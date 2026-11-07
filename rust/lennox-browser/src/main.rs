//! lennox-browser: with the `gui` feature it opens the browser window; the commands below work without it.
//!   lennox-browser dl URL... [--dir D] [--segments N] [--limit KB/S]   download like a download manager
//!   lennox-browser resolve TEXT                                         what the address bar would load
//!   lennox-browser import-zen                                           copy bookmarks and history from Zen

use lennox_browser::{adblock, download, drm, grab, store, url, vault, zen};
use std::path::PathBuf;
use std::sync::atomic::Ordering;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

fn now() -> i64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs() as i64).unwrap_or(0)
}

fn data_dir() -> PathBuf {
    let base = std::env::var("XDG_DATA_HOME").map(PathBuf::from).unwrap_or_else(|_| PathBuf::from(std::env::var("HOME").unwrap_or_default()).join(".local/share"));
    base.join("lennox/browser")
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match args.first().map(String::as_str) {
        Some("resolve") => {
            let text = args[1..].join(" ");
            let target = url::resolve(&text);
            println!("{target}{}", if drm::needs_drm(&target) { "  (needs DRM: opens in Zen)" } else if adblock::Blocker::built_in().blocks_url(&target) { "  (blocked as an ad)" } else { "" });
        }
        Some("import-zen") => {
            let home = PathBuf::from(std::env::var("HOME").unwrap_or_default());
            let Some(places) = zen::find_places(&home) else { return eprintln!("No Zen profile found.") };
            let s = store::Store::open(&data_dir().join("browser.sqlite")).expect("store");
            match zen::import(&places, &s, now()) {
                Ok((b, h)) => println!("Imported {b} bookmarks and {h} history pages from Zen."),
                Err(e) => eprintln!("Import failed: {e}"),
            }
        }
        Some("adblock-rules") => println!("{}", adblock::Blocker::built_in().content_rules_json()),
        Some("passwords") => passwords(&args[1..]),
        Some("grab") if args.len() > 1 => {
            let dir = PathBuf::from(std::env::var("HOME").unwrap_or_default()).join("Downloads/Videos");
            let status = std::process::Command::new("yt-dlp").args(grab::args(&args[1], &dir)).status();
            if status.map(|s| !s.success()).unwrap_or(true) {
                eprintln!("yt-dlp failed or is not installed (sudo pacman -S yt-dlp)");
            }
        }
        Some("pip") if args.len() > 1 => {
            let _ = std::process::Command::new("mpv").args(grab::pip_args(&args[1])).spawn();
        }
        Some("dl") => dl(&args[1..]),
        #[cfg(feature = "gui")]
        None => gui::run(),
        #[cfg(not(feature = "gui"))]
        None => eprintln!("This build has no window (it needs the gui feature and webkitgtk-6.0). Commands: dl, resolve, import-zen"),
        _ => {
            eprintln!("usage: lennox-browser dl URL... | grab URL | pip URL | passwords add|list|get | resolve TEXT | import-zen | adblock-rules");
            std::process::exit(2);
        }
    }
}

fn dl(args: &[String]) {
    let (mut urls, mut dir, mut segs, mut limit) = (vec![], PathBuf::from(std::env::var("HOME").unwrap_or_default()).join("Downloads"), download::DEFAULT_SEGMENTS, 0u64);
    let mut sort = true;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--dir" => { i += 1; dir = PathBuf::from(&args[i]); sort = false; }
            "--segments" => { i += 1; segs = args[i].parse().unwrap_or(segs); }
            "--limit" => { i += 1; limit = args[i].parse::<u64>().unwrap_or(0) * 1024; }
            u => urls.push(u.to_string()),
        }
        i += 1;
    }
    for u in urls {
        let target = if sort { dir.join(download::category(&download::filename_from(&u, None))) } else { dir.clone() };
        let control = download::Control::new(limit);
        let c = control.clone();
        let watcher = std::thread::spawn(move || loop {
            std::thread::sleep(Duration::from_millis(500));
            let (d, t) = (c.done_bytes.load(Ordering::Relaxed), c.total_bytes.load(Ordering::Relaxed));
            if t > 0 { eprint!("\r{:>3}%  {:.1} / {:.1} MB ", d * 100 / t, d as f64 / 1e6, t as f64 / 1e6); }
            if c.pause.load(Ordering::Relaxed) || (t > 0 && d >= t) { break; }
        });
        match download::run(&u, &target, segs, &control) {
            Ok(download::Outcome::Done(p)) => println!("\nSaved {}", p.display()),
            Ok(download::Outcome::Paused) => println!("\nPaused"),
            Err(e) => eprintln!("\nFailed: {e}"),
        }
        control.pause.store(true, Ordering::Relaxed);
        let _ = watcher.join();
    }
}

#[cfg(feature = "gui")]
mod gui;

fn passwords(args: &[String]) {
    let dir = data_dir();
    let v = match vault::Vault::open(&dir.join("vault.sqlite"), &dir.join("vault.key")) {
        Ok(v) => v,
        Err(e) => return eprintln!("vault: {e}"),
    };
    match args.iter().map(String::as_str).collect::<Vec<_>>().as_slice() {
        ["add", host, user, password] => match v.save(host, user, password) {
            Ok(()) => println!("Saved {user} for {host}"),
            Err(e) => eprintln!("{e}"),
        },
        ["list"] => v.hosts().unwrap_or_default().iter().for_each(|(h, u)| println!("{h}  {u}")),
        ["get", host] => match v.for_host(host) {
            Ok(logins) => logins.iter().for_each(|l| println!("{}  {}  {}", l.host, l.user, l.password)),
            Err(e) => eprintln!("{e}"),
        },
        ["remove", host, user] => println!("{}", if v.remove(host, user).unwrap_or(false) { "Removed" } else { "Not found" }),
        _ => eprintln!("usage: lennox-browser passwords add HOST USER PASSWORD | list | get HOST | remove HOST USER"),
    }
}
