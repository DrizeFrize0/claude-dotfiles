//! `lennox-fast sysmon waybar`: the system monitor bar item. Same output as the Python
//! version (lennox.sysmon). When the NVIDIA chip is awake, Python asks it for details.

use crate::python;
use std::collections::HashMap;
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::thread::sleep;
use std::time::Duration;

const WARM: f64 = 75.0;
const HOT: f64 = 88.0;

fn read(p: &Path) -> Option<String> {
    fs::read_to_string(p).ok().map(|s| s.trim().to_string())
}

fn sorted_children(dir: &Path, prefix: &str) -> Vec<PathBuf> {
    let mut v: Vec<PathBuf> = fs::read_dir(dir)
        .map(|it| {
            it.flatten()
                .filter(|e| e.file_name().to_string_lossy().starts_with(prefix))
                .map(|e| e.path())
                .collect()
        })
        .unwrap_or_default();
    v.sort();
    v
}

enum Gpu {
    None,
    Asleep,
    Awake,
}

fn gpu(sys: &Path) -> Gpu {
    for dev in sorted_children(&sys.join("bus/pci/devices"), "") {
        if read(&dev.join("vendor")).as_deref() == Some("0x10de") {
            let class = read(&dev.join("class")).unwrap_or_default();
            if class.starts_with("0x0300") || class.starts_with("0x0302") {
                return if read(&dev.join("power/runtime_status")).as_deref() == Some("suspended") {
                    Gpu::Asleep
                } else {
                    Gpu::Awake
                };
            }
        }
    }
    Gpu::None
}

fn fans(sys: &Path) -> Vec<i64> {
    let mut out = vec![];
    for mon in sorted_children(&sys.join("class/hwmon"), "hwmon") {
        for f in sorted_children(&mon, "fan") {
            if f.to_string_lossy().ends_with("_input") {
                if let Some(rpm) = read(&f).and_then(|s| s.parse::<i64>().ok()) {
                    if rpm > 0 {
                        out.push(rpm);
                    }
                }
            }
        }
    }
    out
}

fn battery_watts(sys: &Path) -> Option<f64> {
    for bat in sorted_children(&sys.join("class/power_supply"), "BAT") {
        if read(&bat.join("status")).as_deref() != Some("Discharging") {
            continue;
        }
        if let Some(p) = read(&bat.join("power_now")) {
            if let Ok(v) = p.parse::<i64>() {
                return Some(v as f64 / 1e6);
            }
            continue;
        }
        let c = read(&bat.join("current_now")).and_then(|s| s.parse::<i64>().ok());
        let v = read(&bat.join("voltage_now")).and_then(|s| s.parse::<i64>().ok());
        if let (Some(c), Some(v)) = (c, v) {
            return Some(c as f64 * v as f64 / 1e12);
        }
    }
    None
}

fn cpu_temp(sys: &Path) -> Option<f64> {
    let mut found: HashMap<String, f64> = HashMap::new();
    for mon in sorted_children(&sys.join("class/hwmon"), "hwmon") {
        if let (Some(name), Some(t)) = (read(&mon.join("name")), read(&mon.join("temp1_input")).and_then(|s| s.parse::<i64>().ok())) {
            found.entry(name).or_insert(t as f64 / 1000.0);
        }
    }
    for name in ["coretemp", "k10temp", "zenpower", "cpu_thermal", "acpitz"] {
        if let Some(t) = found.get(name) {
            return Some(*t);
        }
    }
    for zone in sorted_children(&sys.join("class/thermal"), "thermal_zone") {
        if let Some(t) = read(&zone.join("temp")).and_then(|s| s.parse::<i64>().ok()) {
            let t = t as f64 / 1000.0;
            if t > 0.0 && t < 150.0 {
                return Some(t);
            }
        }
    }
    None
}

fn memory(proc_: &Path) -> Option<(f64, f64, f64)> {
    let text = fs::read_to_string(proc_.join("meminfo")).ok()?;
    let mut info: HashMap<&str, i64> = HashMap::new();
    for line in text.lines() {
        let (k, rest) = line.split_once(':')?;
        info.insert(k, rest.split_whitespace().next()?.parse().ok()?);
    }
    let total = *info.get("MemTotal")?;
    let avail = *info.get("MemAvailable")?;
    if total == 0 {
        return None;
    }
    let used = total - avail;
    Some((100.0 * used as f64 / total as f64, used as f64 / 1048576.0, total as f64 / 1048576.0))
}

fn cpu_sample(proc_: &Path) -> Option<(i64, i64)> {
    let text = fs::read_to_string(proc_.join("stat")).ok()?;
    let f: Vec<i64> = text.lines().next()?.split_whitespace().skip(1).map(|x| x.parse().unwrap_or(0)).collect();
    if f.len() < 4 {
        return None;
    }
    Some((f.iter().sum(), f[3] + f.get(4).copied().unwrap_or(0)))
}

fn proc_times(proc_: &Path) -> HashMap<PathBuf, (String, i64)> {
    let mut out = HashMap::new();
    let Ok(it) = fs::read_dir(proc_) else { return out };
    for e in it.flatten() {
        if !e.file_name().to_string_lossy().chars().next().is_some_and(|c| c.is_ascii_digit()) {
            continue;
        }
        let stat = e.path().join("stat");
        let Some(raw) = fs::read_to_string(&stat).ok().filter(|s| !s.is_empty()) else { continue };
        let (Some(a), Some(b)) = (raw.find('('), raw.rfind(')')) else { continue };
        let rest: Vec<&str> = raw[b + 2..].split_whitespace().collect();
        if rest.len() > 12 {
            if let (Ok(u), Ok(s)) = (rest[11].parse::<i64>(), rest[12].parse::<i64>()) {
                out.insert(stat, (raw[a + 1..b].to_string(), u + s));
            }
        }
    }
    out
}

fn json_str(s: &str) -> String {
    let mut o = String::from("\"");
    for c in s.chars() {
        match c {
            '"' => o.push_str("\\\""),
            '\\' => o.push_str("\\\\"),
            '\n' => o.push_str("\\n"),
            '\r' => o.push_str("\\r"),
            '\t' => o.push_str("\\t"),
            c if (c as u32) < 0x20 => o.push_str(&format!("\\u{:04x}", c as u32)),
            c => o.push(c),
        }
    }
    o.push('"');
    o
}

pub fn run(args: &[String]) {
    let mode = args.first().map(String::as_str).unwrap_or("text");
    if mode != "waybar" {
        python("lennox.sysmon", args);
    }
    let sys = PathBuf::from(env::var("LENNOX_SYS").unwrap_or_else(|_| "/sys".into()));
    let proc_ = PathBuf::from(env::var("LENNOX_PROC").unwrap_or_else(|_| "/proc".into()));
    let gpu_state = gpu(&sys);
    if let Gpu::Awake = gpu_state {
        python("lennox.sysmon", args); // asking the GPU for its details stays in Python
    }
    // CPU use and the busiest programs over half a second
    let c1 = cpu_sample(&proc_);
    let before = proc_times(&proc_);
    sleep(Duration::from_millis(500));
    let c2 = cpu_sample(&proc_);
    let after = proc_times(&proc_);
    let cpu = match (c1, c2) {
        (Some(a), Some(b)) if b.0 > a.0 => {
            let busy = (b.0 - a.0) - (b.1 - a.1);
            Some((100.0 * busy as f64 / (b.0 - a.0) as f64).clamp(0.0, 100.0))
        }
        (Some(_), Some(_)) => Some(0.0),
        _ => None,
    };
    let mut by_name: HashMap<String, f64> = HashMap::new();
    for (key, (name, t1)) in &after {
        if let Some((n0, t0)) = before.get(key) {
            if n0 == name {
                *by_name.entry(name.clone()).or_insert(0.0) += (*t1 - *t0) as f64 / 100.0 / 0.5 * 100.0;
            }
        }
    }
    let mut top: Vec<(f64, String)> = by_name.into_iter().filter(|(_, v)| *v >= 1.0).map(|(k, v)| (v, k)).collect();
    top.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap().then_with(|| b.1.cmp(&a.1)));
    top.truncate(3);

    let temp = cpu_temp(&sys);
    let mut parts = vec![];
    if let Some(t) = temp {
        parts.push(format!("󰔏 {t:.0}°"));
    } else if let Some(c) = cpu {
        parts.push(format!("󰻠 {c:.0}%"));
    }
    let mut tip: Vec<String> = vec![];
    if let Some(c) = cpu {
        let mut line = format!("CPU  {c:.0}%");
        if let Some(t) = temp {
            line += &format!("  ·  {t:.0}°C");
        }
        tip.push(line);
    }
    if let Gpu::Asleep = gpu_state {
        tip.push("NVIDIA GPU  asleep (saving battery)".into());
    }
    if let Some((p, used, total)) = memory(&proc_) {
        tip.push(format!("Memory  {used:.1} of {total:.0} GB  ({p:.0}%)"));
    }
    let f = fans(&sys);
    if !f.is_empty() {
        tip.push(format!("Fans  {}", f.iter().map(|r| format!("{r} rpm")).collect::<Vec<_>>().join(", ")));
    }
    if let Some(w) = battery_watts(&sys) {
        tip.push(format!("Battery use  {w:.1} W"));
    }
    if !top.is_empty() {
        tip.push(String::new());
        tip.push("Busiest right now:".into());
        for (v, n) in &top {
            tip.push(format!("  {n}  {v:.0}%"));
        }
    }
    let hottest = temp.unwrap_or(0.0);
    let state = if hottest >= HOT { "hot" } else if hottest >= WARM { "warm" } else { "cool" };
    if state == "hot" {
        tip.push(String::new());
        tip.push("Very hot: the laptop will slow itself down. Check the vents aren't covered.".into());
    }
    tip.push(String::new());
    tip.push("Click for the full monitor (SUPER + CTRL + ESC)".into());
    println!(
        "{{\"text\": {}, \"tooltip\": {}, \"class\": \"{}\", \"percentage\": {}}}",
        json_str(&parts.join("  ")),
        json_str(&tip.join("\n")),
        state,
        cpu.unwrap_or(0.0).round_ties_even() as i64
    );
}
