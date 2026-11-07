//! lennox-fast: answers the bar items that run every few seconds in about a millisecond.
//! It only handles the quiet case (nothing downloading, no timers). For anything else
//! it runs the Python code, so behaviour never changes: `lennox-fast downloads|clock [args]`.

use std::env;
use std::fs;
use std::os::unix::process::CommandExt;
use std::path::PathBuf;
use std::process::Command;

const EMPTY: &str = "{\"text\": \"\"}";
const PARTIAL: [&str; 4] = [".crdownload", ".part", ".opdownload", ".download"];

fn home() -> PathBuf {
    PathBuf::from(env::var("HOME").unwrap_or_else(|_| "/".into()))
}

fn dir(var: &str, fallback: &str) -> PathBuf {
    match env::var(var) {
        Ok(v) if !v.is_empty() => PathBuf::from(v),
        _ => home().join(fallback),
    }
}

fn squeeze(text: &str) -> String {
    text.chars().filter(|c| !c.is_whitespace()).collect()
}

/// The text of one top-level `"key": { ... }` block (settings.json has no nested braces in these).
fn block<'a>(compact: &'a str, key: &str) -> Option<&'a str> {
    let start = compact.find(&format!("\"{key}\":{{"))? + key.len() + 4;
    let end = compact[start..].find('}')?;
    Some(&compact[start..start + end])
}

/// Quiet means: nothing to show. `None` means "not sure", so Python decides.
fn downloads_quiet() -> Option<bool> {
    let settings = dir("XDG_CONFIG_HOME", ".config").join("lennox/settings.json");
    let compact = fs::read_to_string(settings).map(|t| squeeze(&t)).unwrap_or_default();
    let section = block(&compact, "downloads").unwrap_or("");
    if section.contains("\"on\":false") {
        return Some(true);
    }
    if !section.is_empty() && !section.contains("\"folder\":\"\"") {
        return None; // a custom folder: let Python handle it
    }
    let runtime = env::var("XDG_RUNTIME_DIR").unwrap_or_else(|_| "/tmp".into());
    if let Ok(state) = fs::read_to_string(PathBuf::from(runtime).join("lennox/downloads.json")) {
        let state = squeeze(&state);
        if !state.contains("\"partials\":{}") {
            return None; // something was downloading: Python finishes the story
        }
        if state.contains("\"last\":\"") {
            // A finished download stays in the bar for 60 seconds
            let stamp = state.split("\"last_time\":").nth(1)?;
            let number: String = stamp.chars().take_while(|c| c.is_ascii_digit() || *c == '.').collect();
            let then: f64 = number.parse().ok()?;
            let now = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).ok()?.as_secs_f64();
            if now - then < 65.0 {
                return None;
            }
        }
    }
    let entries = fs::read_dir(home().join("Downloads")).ok()?;
    for e in entries.flatten() {
        let name = e.file_name().to_string_lossy().into_owned();
        if PARTIAL.iter().any(|p| name.ends_with(p)) {
            return None;
        }
    }
    Some(true)
}

fn clock_quiet() -> Option<bool> {
    let file = dir("XDG_STATE_HOME", ".local/state").join("lennox/clock.json");
    let text = match fs::read_to_string(file) {
        Ok(t) => squeeze(&t),
        Err(_) => return Some(true), // no clock data yet
    };
    let quiet = text.contains("\"timers\":[]")
        && text.contains("\"reminders\":[]")
        && text.contains("\"ringing\":[]")
        && text.contains("\"start\":null")
        && !text.contains("\"enabled\":true");
    if quiet { Some(true) } else { None }
}

fn python(module: &str, args: &[String]) -> ! {
    let lib = home().join(".local/share/lennox/python");
    let err = Command::new("python3").arg("-m").arg(module).args(args).env("PYTHONPATH", lib).exec();
    eprintln!("lennox-fast: cannot run python3: {err}");
    std::process::exit(1);
}

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    let (which, rest) = match args.split_first() {
        Some((w, r)) => (w.as_str(), r.to_vec()),
        None => {
            eprintln!("usage: lennox-fast downloads|clock [waybar]");
            std::process::exit(2);
        }
    };
    let waybar = rest.first().map(String::as_str).unwrap_or("waybar") == "waybar";
    match which {
        "downloads" if waybar => {
            if downloads_quiet() == Some(true) {
                println!("{EMPTY}");
                return;
            }
            python("lennox.downloads", &["waybar".to_string()]);
        }
        "clock" if waybar => {
            if clock_quiet() == Some(true) {
                println!("{EMPTY}");
                return;
            }
            python("lennox.clock", &["waybar".to_string()]);
        }
        "downloads" => python("lennox.downloads", &rest),
        "clock" => python("lennox.clock", &rest),
        _ => {
            eprintln!("usage: lennox-fast downloads|clock [waybar]");
            std::process::exit(2);
        }
    }
}
