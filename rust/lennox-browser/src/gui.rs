//! The browser window: vertical tabs on the left, WebKitGTK pages on the right.
//! Needs `--features gui` and the webkitgtk-6.0 package. GTK themes it, so it follows the Lennox colors.

use gtk::prelude::*;
use gtk::{gio, glib};
use gtk4 as gtk;
use lennox_browser::prefs::{Prefs, Verdict};
use lennox_browser::{adblock, drm, grab, start, store, ua, url, vault};
use std::cell::{Cell, RefCell};
use std::path::PathBuf;
use std::rc::Rc;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use webkit6::prelude::*;
use webkit6::{NavigationPolicyDecision, NetworkSession, PolicyDecisionType, UserContentManager, WebView};

const SLEEP_AFTER: Duration = Duration::from_secs(600);

struct Tab {
    holder: gtk::Paned,
    view: WebView,
    split: RefCell<Option<WebView>>,
    row: gtk::Label,
    used: Cell<Instant>,
    slept_url: RefCell<Option<String>>,
}

struct Browser {
    stack: gtk::Stack,
    list: gtk::ListBox,
    entry: gtk::Entry,
    tabs: RefCell<Vec<Rc<Tab>>>,
    session: NetworkSession,
    content: UserContentManager,
    store: store::Store,
    vault: Option<vault::Vault>,
    prefs: RefCell<Prefs>,
    prefs_path: PathBuf,
    hub: Option<String>,
}

fn now() -> i64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs() as i64).unwrap_or(0)
}

fn lennox_get(key: &str) -> String {
    std::process::Command::new("lennox-get").arg(key).output().map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string()).unwrap_or_default()
}

fn js_str(s: &str) -> String {
    let mut o = String::from("\"");
    for c in s.chars() {
        match c {
            '"' => o.push_str("\\\""),
            '\\' => o.push_str("\\\\"),
            '\n' => o.push_str("\\n"),
            '\r' => {}
            '<' => o.push_str("\\u003c"),
            c => o.push(c),
        }
    }
    o.push('"');
    o
}

fn run_js(view: &WebView, script: &str) {
    view.evaluate_javascript(script, None, None, gio::Cancellable::NONE, |_| {});
}

fn host_of_view(view: &WebView) -> String {
    view.uri().and_then(|u| url::host_of(u.as_str())).unwrap_or_default()
}

impl Browser {
    fn current(&self) -> Option<Rc<Tab>> {
        let row = self.list.selected_row()?;
        self.tabs.borrow().get(row.index() as usize).cloned()
    }

    fn make_view(self: &Rc<Self>) -> WebView {
        let view = WebView::builder().network_session(&self.session).user_content_manager(&self.content).build();
        if let Some(settings) = WebViewExt::settings(&view) {
            settings.set_enable_developer_extras(true);
            settings.set_enable_back_forward_navigation_gestures(true);
            settings.set_user_agent(Some(ua::default_agent()));
        }
        view.set_hexpand(true);
        view.set_vexpand(true);

        // Google sites get a Firefox tag (sign-in), DRM sites open in Zen
        view.connect_decide_policy(|view, decision, kind| {
            if kind == PolicyDecisionType::NavigationAction {
                if let Some(nav) = decision.downcast_ref::<NavigationPolicyDecision>() {
                    if let Some(uri) = nav.navigation_action().and_then(|mut a| a.request()).and_then(|r| r.uri()) {
                        if let Some(settings) = WebViewExt::settings(view) {
                            settings.set_user_agent(Some(ua::for_url(uri.as_str())));
                        }
                        if drm::needs_drm(uri.as_str()) {
                            let _ = std::process::Command::new("flatpak").args(["run", "app.zen_browser.zen", uri.as_str()]).spawn();
                            decision.ignore();
                            return true;
                        }
                    }
                }
            }
            false
        });

        // Camera, microphone, location and notifications: your saved answer, or ask once
        let b = self.clone();
        view.connect_permission_request(move |view, request| {
            let what = if request.is::<webkit6::GeolocationPermissionRequest>() {
                "location"
            } else if request.is::<webkit6::NotificationPermissionRequest>() {
                "notifications"
            } else if let Some(m) = request.downcast_ref::<webkit6::UserMediaPermissionRequest>() {
                if m.is_for_video_device() { "camera" } else { "microphone" }
            } else {
                return false;
            };
            let host = host_of_view(view);
            let verdict = b.prefs.borrow().verdict(&host, what);
            match verdict {
                Verdict::Allow => request.allow(),
                Verdict::Deny => request.deny(),
                Verdict::Ask => {
                    let dialog = gtk::AlertDialog::builder().message(format!("{host} wants to use your {what}")).buttons(["Block", "Allow"]).default_button(0).cancel_button(0).build();
                    let window = view.root().and_then(|r| r.downcast::<gtk::Window>().ok());
                    let (b2, req, host2) = (b.clone(), request.clone(), host.clone());
                    dialog.choose(window.as_ref(), gio::Cancellable::NONE, move |answer| {
                        let allow = matches!(answer, Ok(1));
                        if allow { req.allow() } else { req.deny() }
                        let mut p = b2.prefs.borrow_mut();
                        p.sites.insert((host2, what.to_string()), if allow { Verdict::Allow } else { Verdict::Deny });
                        let _ = p.save(&b2.prefs_path);
                    });
                }
            }
            true
        });
        view
    }

    fn open(self: &Rc<Self>, target: &str) {
        let view = self.make_view();
        let holder = gtk::Paned::new(gtk::Orientation::Horizontal);
        holder.set_start_child(Some(&view));
        holder.set_resize_start_child(true);
        holder.set_hexpand(true);
        holder.set_vexpand(true);
        let label = gtk::Label::builder().label("New tab").xalign(0.0).ellipsize(gtk::pango::EllipsizeMode::End).build();
        let tab = Rc::new(Tab { holder: holder.clone(), view: view.clone(), split: RefCell::new(None), row: label.clone(), used: Cell::new(Instant::now()), slept_url: RefCell::new(None) });
        let name = format!("tab{}-{}", self.tabs.borrow().len(), now());
        self.stack.add_named(&holder, Some(&name));
        self.list.append(&label);
        self.tabs.borrow_mut().push(tab.clone());

        let b = self.clone();
        let t = tab.clone();
        view.connect_title_notify(move |v| {
            let title = v.title().map(|s| s.to_string()).unwrap_or_default();
            t.row.set_label(if title.is_empty() { "New tab" } else { &title });
            if let Some(uri) = v.uri() {
                let _ = b.store.visit(uri.as_str(), &title, now());
            }
        });
        let b = self.clone();
        let v2 = view.clone();
        view.connect_uri_notify(move |v| {
            if b.current().map(|c| c.view == v2).unwrap_or(false) {
                b.entry.set_text(&v.uri().map(|u| u.to_string()).unwrap_or_default());
            }
        });
        self.load(&view, target);
        if let Some(row) = self.list.row_at_index(self.tabs.borrow().len() as i32 - 1) {
            self.list.select_row(Some(&row));
        }
    }

    fn load(&self, view: &WebView, input: &str) {
        if input.is_empty() || input == "lennox:start" {
            let tiles = self.store.most_visited(8).unwrap_or_default();
            view.load_html(&start::page(&tiles, self.hub.as_deref()), Some("lennox:start"));
        } else {
            view.load_uri(&url::resolve(input));
        }
    }

    fn close_current(&self) {
        let Some(row) = self.list.selected_row() else { return };
        let i = row.index() as usize;
        if self.tabs.borrow().len() <= 1 {
            return;
        }
        let tab = self.tabs.borrow_mut().remove(i);
        self.stack.remove(&tab.holder);
        self.list.remove(&row);
        if let Some(next) = self.list.row_at_index(i.saturating_sub(1) as i32) {
            self.list.select_row(Some(&next));
        }
    }

    /// Two pages side by side in one tab (press again to go back to one).
    fn toggle_split(self: &Rc<Self>) {
        let Some(tab) = self.current() else { return };
        if tab.split.borrow().is_some() {
            tab.holder.set_end_child(gtk::Widget::NONE);
            *tab.split.borrow_mut() = None;
        } else {
            let second = self.make_view();
            self.load(&second, "lennox:start");
            tab.holder.set_end_child(Some(&second));
            tab.holder.set_resize_end_child(true);
            *tab.split.borrow_mut() = Some(second);
        }
    }

    fn save_login_dialog(self: &Rc<Self>, window: &gtk::ApplicationWindow) {
        let (Some(tab), true) = (self.current(), self.vault.is_some()) else { return };
        let host = host_of_view(&tab.view);
        let user = gtk::Entry::builder().placeholder_text("Username or email").build();
        let pass = gtk::PasswordEntry::builder().placeholder_text("Password").show_peek_icon(true).build();
        let save = gtk::Button::with_label("Save");
        let boxed = gtk::Box::new(gtk::Orientation::Vertical, 8);
        for w in [&gtk::Label::new(Some(&format!("Save a login for {host}"))) as &gtk::Widget, user.upcast_ref(), pass.upcast_ref(), save.upcast_ref()] {
            boxed.append(w);
        }
        boxed.set_margin_top(14); boxed.set_margin_bottom(14); boxed.set_margin_start(14); boxed.set_margin_end(14);
        let dialog = gtk::Window::builder().transient_for(window).modal(true).title("Save login").child(&boxed).default_width(340).build();
        let b = self.clone();
        let d = dialog.clone();
        save.connect_clicked(move |_| {
            if let Some(v) = &b.vault {
                let _ = v.save(&host, user.text().as_str(), pass.text().as_str());
            }
            d.close();
        });
        dialog.present();
    }

    fn fill_login(&self) {
        let (Some(tab), Some(v)) = (self.current(), &self.vault) else { return };
        let Ok(logins) = v.for_host(&host_of_view(&tab.view)) else { return };
        if let Some(l) = logins.first() {
            let script = format!(
                r#"(function(u,p){{const set=(el,v)=>{{if(!el)return;const d=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');d.set.call(el,v);el.dispatchEvent(new Event('input',{{bubbles:true}}));el.dispatchEvent(new Event('change',{{bubbles:true}}));}};
const pw=document.querySelector('input[type=password]');
const user=document.querySelector('input[type=email],input[autocomplete=username],input[name*=user i],input[name*=email i],input[type=text]');
set(user,u);set(pw,p);}})({},{})"#,
                js_str(&l.user),
                js_str(&l.password)
            );
            run_js(&tab.view, &script);
        }
    }
}

pub fn run() {
    let app = gtk::Application::builder().application_id("lennox.browser").build();
    app.connect_activate(build);
    app.run_with_args::<&str>(&[]);
}

fn build(app: &gtk::Application) {
    let data = std::env::var("XDG_DATA_HOME").map(PathBuf::from).unwrap_or_else(|_| PathBuf::from(std::env::var("HOME").unwrap_or_default()).join(".local/share")).join("lennox/browser");
    let _ = std::fs::create_dir_all(&data);
    let prefs_path = data.join("prefs.txt");
    let mut prefs = Prefs::load(&prefs_path);
    // Lennox Settings > Extras > Lennox Browser: what to wipe each time it starts and closes
    prefs.clear_cookies |= lennox_get("browser.clear_cookies") == "true";
    prefs.clear_history |= lennox_get("browser.clear_history") == "true";
    prefs.clear_cache |= lennox_get("browser.clear_cache") == "true";
    if prefs.clear_cookies {
        let _ = std::fs::remove_dir_all(data.join("web"));
    }
    if prefs.clear_cache {
        let _ = std::fs::remove_dir_all(data.join("cache"));
    }
    let session = NetworkSession::new(Some(data.join("web").to_str().unwrap_or("")), Some(data.join("cache").to_str().unwrap_or("")));
    // Strict privacy that still lets Google sign in: third parties only keep cookies for sites you visited yourself
    if let Some(cookies) = session.cookie_manager() {
        cookies.set_accept_policy(webkit6::CookieAcceptPolicy::NoThirdParty);
    }
    let content = UserContentManager::new();
    let filters = webkit6::UserContentFilterStore::new(data.join("filters").to_str().unwrap_or(""));
    let rules = glib::Bytes::from_owned(adblock::Blocker::built_in().content_rules_json().into_bytes());
    let content2 = content.clone();
    glib::spawn_future_local(async move {
        if let Ok(filter) = filters.save_future("lennox-ads", &rules).await {
            content2.add_filter(&filter);
        }
    });
    // Downloads go to the Lennox download manager: several segments at once, resume, sorted folders
    session.connect_download_started(|_, download| {
        if let Some(uri) = download.request().and_then(|r| r.uri()) {
            let _ = std::process::Command::new(std::env::current_exe().unwrap_or_else(|_| "lennox-browser".into())).args(["dl", uri.as_str()]).spawn();
        }
        download.cancel();
    });

    let stack = gtk::Stack::new();
    let list = gtk::ListBox::builder().css_classes(["navigation-sidebar"]).vexpand(true).build();
    let entry = gtk::Entry::builder().hexpand(true).placeholder_text("Search or type an address").build();
    let history = store::Store::open(&data.join("browser.sqlite")).expect("browser.sqlite");
    if prefs.clear_history {
        let _ = history.clear_history();
    }
    let browser = Rc::new(Browser {
        stack: stack.clone(), list: list.clone(), entry: entry.clone(), tabs: RefCell::new(vec![]), session, content, store: history,
        vault: vault::Vault::open(&data.join("vault.sqlite"), &data.join("vault.key")).ok(), prefs: RefCell::new(prefs), prefs_path,
        hub: Some(lennox_get("hub.url")).filter(|h| !h.is_empty()).map(|h| url::resolve(&h)),
    });

    let button = |icon: &str, tip: &str| {
        let b = gtk::Button::from_icon_name(icon);
        b.set_tooltip_text(Some(tip));
        b
    };
    let new_tab = gtk::Button::with_label("New tab");
    let hub_btn = gtk::Button::with_label("Jado's hub");
    hub_btn.set_sensitive(browser.hub.is_some());
    let back = button("go-previous-symbolic", "Back");
    let forward = button("go-next-symbolic", "Forward");
    let reload = button("view-refresh-symbolic", "Reload");
    let star = button("starred-symbolic", "Bookmark this page");
    let key_save = button("document-save-symbolic", "Save a login for this site");
    let key_fill = button("dialog-password-symbolic", "Fill in the saved login");
    let split = button("view-dual-symbolic", "Split view");
    let pip = button("video-display-symbolic", "Float the video (picture in picture)");
    let grabber = button("folder-download-symbolic", "Download the video on this page");

    let side = gtk::Box::new(gtk::Orientation::Vertical, 6);
    side.set_width_request(230);
    side.set_margin_top(8); side.set_margin_bottom(8); side.set_margin_start(8); side.set_margin_end(8);
    side.append(&new_tab);
    side.append(&hub_btn);
    side.append(&gtk::ScrolledWindow::builder().child(&list).vexpand(true).build());

    let bar = gtk::Box::new(gtk::Orientation::Horizontal, 6);
    bar.set_margin_top(8); bar.set_margin_bottom(8); bar.set_margin_start(8); bar.set_margin_end(8);
    for w in [&back, &forward, &reload] { bar.append(w); }
    bar.append(&entry);
    for w in [&star, &key_fill, &key_save, &split, &pip, &grabber] { bar.append(w); }
    let main = gtk::Box::new(gtk::Orientation::Vertical, 0);
    main.append(&bar);
    main.append(&stack);
    let root = gtk::Box::new(gtk::Orientation::Horizontal, 0);
    root.append(&side);
    root.append(&gtk::Separator::new(gtk::Orientation::Vertical));
    root.append(&main);

    let window = gtk::ApplicationWindow::builder().application(app).title("Lennox Browser").default_width(1280).default_height(800).child(&root).build();

    { let b = browser.clone(); new_tab.connect_clicked(move |_| b.open("lennox:start")); }
    { let b = browser.clone(); hub_btn.connect_clicked(move |_| { if let Some(h) = b.hub.clone() { b.open(&h); } }); }
    { let b = browser.clone(); back.connect_clicked(move |_| if let Some(t) = b.current() { t.view.go_back(); }); }
    { let b = browser.clone(); forward.connect_clicked(move |_| if let Some(t) = b.current() { t.view.go_forward(); }); }
    { let b = browser.clone(); reload.connect_clicked(move |_| if let Some(t) = b.current() { t.view.reload(); }); }
    { let b = browser.clone(); star.connect_clicked(move |_| if let Some(t) = b.current() {
        if let Some(uri) = t.view.uri() {
            let u = uri.to_string();
            if b.store.is_bookmarked(&u) { let _ = b.store.remove_bookmark(&u); } else { let _ = b.store.add_bookmark(&u, &t.view.title().map(|s| s.to_string()).unwrap_or_default(), now()); }
        }
    }); }
    { let b = browser.clone(); let w = window.clone(); key_save.connect_clicked(move |_| b.save_login_dialog(&w)); }
    { let b = browser.clone(); key_fill.connect_clicked(move |_| b.fill_login()); }
    { let b = browser.clone(); split.connect_clicked(move |_| b.toggle_split()); }
    { let b = browser.clone(); pip.connect_clicked(move |_| if let Some(t) = b.current() {
        if let Some(uri) = t.view.uri() {
            run_js(&t.view, "document.querySelectorAll('video').forEach(v=>v.pause())");
            let _ = std::process::Command::new("mpv").args(grab::pip_args(uri.as_str())).spawn();
        }
    }); }
    { let b = browser.clone(); grabber.connect_clicked(move |_| if let Some(t) = b.current() {
        if let Some(uri) = t.view.uri() {
            let dir = PathBuf::from(std::env::var("HOME").unwrap_or_default()).join("Downloads/Videos");
            let _ = std::process::Command::new("yt-dlp").args(grab::args(uri.as_str(), &dir)).spawn();
        }
    }); }
    { let b = browser.clone(); entry.connect_activate(move |e| if let Some(t) = b.current() { b.load(&t.view, e.text().as_str()); }); }
    { let b = browser.clone(); list.connect_row_selected(move |_, row| {
        if let Some(row) = row {
            if let Some(tab) = b.tabs.borrow().get(row.index() as usize) {
                tab.used.set(Instant::now());
                if let Some(u) = tab.slept_url.borrow_mut().take() { tab.view.load_uri(&u); }
                b.stack.set_visible_child(&tab.holder);
                b.entry.set_text(&tab.view.uri().map(|u| u.to_string()).unwrap_or_default());
            }
        }
    }); }

    let actions: [(&str, &str, Box<dyn Fn(&Rc<Browser>)>); 8] = [
        ("new-tab", "<Control>t", Box::new(|b| b.open("lennox:start"))),
        ("close-tab", "<Control>w", Box::new(|b| b.close_current())),
        ("focus-address", "<Control>l", Box::new(|b| { b.entry.grab_focus(); })),
        ("reload", "<Control>r", Box::new(|b| if let Some(t) = b.current() { t.view.reload(); })),
        ("back", "<Alt>Left", Box::new(|b| if let Some(t) = b.current() { t.view.go_back(); })),
        ("forward", "<Alt>Right", Box::new(|b| if let Some(t) = b.current() { t.view.go_forward(); })),
        ("devtools", "F12", Box::new(|b| if let Some(t) = b.current() { if let Some(i) = t.view.inspector() { i.show(); } })),
        ("split", "<Control><Shift>s", Box::new(|b| b.toggle_split())),
    ];
    for (name, accel, f) in actions {
        let action = gio::SimpleAction::new(name, None);
        let b = browser.clone();
        action.connect_activate(move |_, _| f(&b));
        window.add_action(&action);
        app.set_accels_for_action(&format!("win.{name}"), &[accel]);
    }

    // Sleeping tabs: pages not used for 10 minutes are unloaded (they come back when you click them)
    { let b = browser.clone(); glib::timeout_add_seconds_local(60, move || {
        let current = b.list.selected_row().map(|r| r.index() as usize);
        for (i, tab) in b.tabs.borrow().iter().enumerate() {
            if Some(i) != current && tab.slept_url.borrow().is_none() && tab.used.get().elapsed() > SLEEP_AFTER {
                if let Some(u) = tab.view.uri() {
                    if u.as_str().starts_with("http") { *tab.slept_url.borrow_mut() = Some(u.to_string()); tab.view.load_uri("about:blank"); }
                }
            }
        }
        glib::ControlFlow::Continue
    }); }

    // Clear on exit
    { let b = browser.clone(); window.connect_close_request(move |_| {
        if b.prefs.borrow().clear_history { let _ = b.store.clear_history(); }
        glib::Propagation::Proceed
    }); }

    browser.open("lennox:start");
    window.present();
}
