//! The browser window: vertical tabs on the left, WebKitGTK pages on the right.
//! Needs `--features gui` and the webkitgtk-6.0 package. GTK themes it, so it follows the Lennox colors.

use gtk4 as gtk;
use gtk::prelude::*;
use gtk::{gio, glib};
use lennox_browser::{adblock, drm, start, store, url};
use std::cell::{Cell, RefCell};
use std::rc::Rc;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use webkit6::prelude::*;
use webkit6::{NavigationPolicyDecision, NetworkSession, PolicyDecisionType, UserContentManager, WebView};

const SLEEP_AFTER: Duration = Duration::from_secs(600);

struct Tab {
    view: WebView,
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
    hub: Option<String>,
}

fn now() -> i64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs() as i64).unwrap_or(0)
}

fn hub_address() -> Option<String> {
    let out = std::process::Command::new("lennox-get").arg("hub.url").output().ok()?;
    let text = String::from_utf8_lossy(&out.stdout).trim().to_string();
    if text.is_empty() { None } else { Some(url::resolve(&text)) }
}

impl Browser {
    fn current(&self) -> Option<Rc<Tab>> {
        let row = self.list.selected_row()?;
        self.tabs.borrow().get(row.index() as usize).cloned()
    }

    fn open(self: &Rc<Self>, target: &str) {
        let view = WebView::builder().network_session(&self.session).user_content_manager(&self.content).build();
        if let Some(settings) = WebViewExt::settings(&view) {
            settings.set_enable_developer_extras(true);
            settings.set_enable_back_forward_navigation_gestures(true);
        }
        view.set_hexpand(true);
        view.set_vexpand(true);
        let label = gtk::Label::builder().label("New tab").xalign(0.0).ellipsize(gtk::pango::EllipsizeMode::End).build();
        let tab = Rc::new(Tab { view: view.clone(), row: label.clone(), used: Cell::new(Instant::now()), slept_url: RefCell::new(None) });
        let name = format!("tab{}", self.tabs.borrow().len() + now() as usize);
        self.stack.add_named(&view, Some(&name));
        self.list.append(&label);
        self.tabs.borrow_mut().push(tab.clone());

        // DRM sites open in Zen; everything else loads here
        view.connect_decide_policy(|_, decision, kind| {
            if kind == PolicyDecisionType::NavigationAction {
                if let Some(nav) = decision.downcast_ref::<NavigationPolicyDecision>() {
                    if let Some(uri) = nav.navigation_action().and_then(|mut a| a.request()).and_then(|r| r.uri()) {
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
        self.stack.remove(&tab.view);
        self.list.remove(&row);
        if let Some(next) = self.list.row_at_index(i.saturating_sub(1) as i32) {
            self.list.select_row(Some(&next));
        }
    }
}

pub fn run() {
    let app = gtk::Application::builder().application_id("lennox.browser").build();
    app.connect_activate(build);
    app.run_with_args::<&str>(&[]);
}

fn build(app: &gtk::Application) {
    let data = std::env::var("XDG_DATA_HOME").map(std::path::PathBuf::from).unwrap_or_else(|_| std::path::PathBuf::from(std::env::var("HOME").unwrap_or_default()).join(".local/share")).join("lennox/browser");
    let _ = std::fs::create_dir_all(&data);
    let session = NetworkSession::new(Some(data.join("web").to_str().unwrap_or("")), Some(data.join("cache").to_str().unwrap_or("")));
    let content = UserContentManager::new();
    // Ads and trackers: WebKit content-blocker rules from the Rust list
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
    let browser = Rc::new(Browser {
        stack: stack.clone(), list: list.clone(), entry: entry.clone(), tabs: RefCell::new(vec![]), session, content,
        store: store::Store::open(&data.join("browser.sqlite")).expect("browser.sqlite"), hub: hub_address(),
    });

    let new_tab = gtk::Button::from_icon_name("tab-new-symbolic");
    let hub_btn = gtk::Button::with_label("Jado's hub");
    hub_btn.set_sensitive(browser.hub.is_some());
    let back = gtk::Button::from_icon_name("go-previous-symbolic");
    let forward = gtk::Button::from_icon_name("go-next-symbolic");
    let reload = gtk::Button::from_icon_name("view-refresh-symbolic");
    let star = gtk::Button::from_icon_name("starred-symbolic");

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
    bar.append(&star);
    let main = gtk::Box::new(gtk::Orientation::Vertical, 0);
    main.append(&bar);
    main.append(&stack);
    let root = gtk::Box::new(gtk::Orientation::Horizontal, 0);
    root.append(&side);
    root.append(&gtk::Separator::new(gtk::Orientation::Vertical));
    root.append(&main);

    let window = gtk::ApplicationWindow::builder().application(app).title("Lennox Browser").default_width(1280).default_height(800).child(&root).build();

    // Buttons
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
    { let b = browser.clone(); entry.connect_activate(move |e| if let Some(t) = b.current() { b.load(&t.view, e.text().as_str()); }); }
    { let b = browser.clone(); list.connect_row_selected(move |_, row| {
        if let Some(row) = row {
            if let Some(tab) = b.tabs.borrow().get(row.index() as usize) {
                tab.used.set(Instant::now());
                if let Some(u) = tab.slept_url.borrow_mut().take() { tab.view.load_uri(&u); }
                b.stack.set_visible_child(&tab.view);
                b.entry.set_text(&tab.view.uri().map(|u| u.to_string()).unwrap_or_default());
            }
        }
    }); }

    // Keyboard: the usual browser shortcuts
    let actions: [(&str, &str, Box<dyn Fn(&Rc<Browser>)>); 7] = [
        ("new-tab", "<Control>t", Box::new(|b| b.open("lennox:start"))),
        ("close-tab", "<Control>w", Box::new(|b| b.close_current())),
        ("focus-address", "<Control>l", Box::new(|b| { b.entry.grab_focus(); })),
        ("reload", "<Control>r", Box::new(|b| if let Some(t) = b.current() { t.view.reload(); })),
        ("back", "<Alt>Left", Box::new(|b| if let Some(t) = b.current() { t.view.go_back(); })),
        ("forward", "<Alt>Right", Box::new(|b| if let Some(t) = b.current() { t.view.go_forward(); })),
        ("devtools", "F12", Box::new(|b| if let Some(t) = b.current() { if let Some(i) = t.view.inspector() { i.show(); } })),
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

    browser.open("lennox:start");
    window.present();
}
