//! Download manager in the style of IDM: one file is split into segments that download at the same
//! time, pause and resume survive a restart, a speed limit, a queue with a schedule, and files
//! sorted into folders by type.

use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::os::unix::fs::FileExt;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

pub const DEFAULT_SEGMENTS: usize = 8;
const CHUNK: usize = 64 * 1024;

#[derive(Debug, PartialEq)]
pub enum Outcome {
    Done(PathBuf),
    Paused,
}

#[derive(Debug)]
pub struct Info {
    pub length: Option<u64>,
    pub ranges: bool,
    pub name: String,
}

/// Shared between the download threads and whoever shows progress or presses pause.
pub struct Control {
    pub pause: AtomicBool,
    pub done_bytes: AtomicU64,
    pub total_bytes: AtomicU64,
    limit_bps: AtomicU64,
    started: Instant,
    sent: AtomicU64,
}

impl Control {
    pub fn new(limit_bps: u64) -> Arc<Self> {
        Arc::new(Control {
            pause: AtomicBool::new(false),
            done_bytes: AtomicU64::new(0),
            total_bytes: AtomicU64::new(0),
            limit_bps: AtomicU64::new(limit_bps),
            started: Instant::now(),
            sent: AtomicU64::new(0),
        })
    }

    pub fn set_limit(&self, bps: u64) {
        self.limit_bps.store(bps, Ordering::Relaxed);
    }

    /// Keeps the whole download (all segments together) under the speed limit.
    fn throttle(&self, bytes: u64) {
        let limit = self.limit_bps.load(Ordering::Relaxed);
        let sent = self.sent.fetch_add(bytes, Ordering::Relaxed) + bytes;
        if limit == 0 {
            return;
        }
        let due = Duration::from_secs_f64(sent as f64 / limit as f64);
        let elapsed = self.started.elapsed();
        if due > elapsed {
            thread::sleep(due - elapsed);
        }
    }
}

pub fn filename_from(url: &str, content_disposition: Option<&str>) -> String {
    if let Some(cd) = content_disposition {
        if let Some(pos) = cd.find("filename=") {
            let n = cd[pos + 9..].trim().trim_matches('"').split(';').next().unwrap_or("").trim_matches('"');
            if !n.is_empty() {
                return sanitize(n);
            }
        }
    }
    let path = url.split(['?', '#']).next().unwrap_or(url);
    let last = path.rsplit('/').next().unwrap_or("");
    if last.is_empty() || !path.contains("://") || path.ends_with('/') {
        "download".into()
    } else {
        sanitize(last)
    }
}

fn sanitize(name: &str) -> String {
    let n: String = name.chars().map(|c| if c == '/' || c == '\\' || c.is_control() { '_' } else { c }).collect();
    let n = n.trim_matches('.').to_string();
    if n.is_empty() { "download".into() } else { n }
}

pub fn probe(url: &str) -> Result<Info, String> {
    let agent = ureq::AgentBuilder::new().timeout(Duration::from_secs(20)).build();
    let head = agent.head(url).call().map_err(|e| e.to_string())?;
    let mut length = head.header("content-length").and_then(|v| v.parse().ok());
    let mut ranges = head.header("accept-ranges").map(|v| v.eq_ignore_ascii_case("bytes")).unwrap_or(false);
    if !ranges {
        // Some servers don't say, but answer a range request
        if let Ok(r) = agent.get(url).set("Range", "bytes=0-0").call() {
            if r.status() == 206 {
                ranges = true;
                if let Some(total) = r.header("content-range").and_then(|v| v.rsplit('/').next()).and_then(|v| v.parse().ok()) {
                    length = Some(total);
                }
            }
        }
    }
    Ok(Info { length, ranges, name: filename_from(url, head.header("content-disposition")) })
}

/// Splits `length` bytes into `n` (start, end inclusive) ranges.
pub fn split(length: u64, n: usize) -> Vec<(u64, u64)> {
    let n = (n.max(1) as u64).min(length.max(1));
    let size = length / n;
    (0..n).map(|i| (i * size, if i == n - 1 { length - 1 } else { (i + 1) * size - 1 })).collect()
}

/// A saved plan: where each segment is (start, end, next byte to fetch).
fn read_state(path: &Path, length: u64) -> Option<Vec<(u64, u64, u64)>> {
    let text = fs::read_to_string(path).ok()?;
    let mut lines = text.lines();
    if lines.next()?.parse::<u64>().ok()? != length {
        return None;
    }
    let segs: Vec<(u64, u64, u64)> = lines
        .filter_map(|l| {
            let mut p = l.split_whitespace().map(|x| x.parse::<u64>());
            Some((p.next()?.ok()?, p.next()?.ok()?, p.next()?.ok()?))
        })
        .collect();
    if segs.is_empty() { None } else { Some(segs) }
}

fn write_state(path: &Path, length: u64, segs: &[(u64, u64, u64)]) {
    let mut text = format!("{length}\n");
    for (s, e, p) in segs {
        text += &format!("{s} {e} {p}\n");
    }
    let tmp = path.with_extension("lennox.tmp");
    if fs::write(&tmp, text).is_ok() {
        let _ = fs::rename(tmp, path);
    }
}

fn unique(dir: &Path, name: &str) -> PathBuf {
    let mut p = dir.join(name);
    let (stem, ext) = match name.rsplit_once('.') {
        Some((s, e)) if !s.is_empty() => (s.to_string(), format!(".{e}")),
        _ => (name.to_string(), String::new()),
    };
    let mut i = 1;
    while p.exists() {
        p = dir.join(format!("{stem} ({i}){ext}"));
        i += 1;
    }
    p
}

/// Downloads `url` into `dir`. Several segments at once when the server allows it.
pub fn run(url: &str, dir: &Path, segments: usize, control: &Arc<Control>) -> Result<Outcome, String> {
    fs::create_dir_all(dir).map_err(|e| e.to_string())?;
    let info = probe(url)?;
    let part = dir.join(format!("{}.part", info.name));
    let state_path = dir.join(format!("{}.lennox", info.name));
    match (info.length, info.ranges) {
        (Some(len), true) if len > 0 => segmented(url, dir, &info.name, &part, &state_path, len, segments, control),
        _ => single(url, dir, &info.name, &part, control),
    }
}

#[allow(clippy::too_many_arguments)]
fn segmented(url: &str, dir: &Path, name: &str, part: &Path, state_path: &Path, len: u64, n: usize, control: &Arc<Control>) -> Result<Outcome, String> {
    let segs = read_state(state_path, len).filter(|_| part.exists()).unwrap_or_else(|| split(len, n).into_iter().map(|(s, e)| (s, e, s)).collect());
    let file = OpenOptions::new().create(true).truncate(false).write(true).open(part).map_err(|e| e.to_string())?;
    file.set_len(len).map_err(|e| e.to_string())?;
    let file = Arc::new(file);
    control.total_bytes.store(len, Ordering::Relaxed);
    control.done_bytes.store(segs.iter().map(|(s, _, p)| p - s).sum(), Ordering::Relaxed);
    let shared = Arc::new(Mutex::new(segs));
    let failed: Arc<Mutex<Option<String>>> = Arc::new(Mutex::new(None));
    let count = shared.lock().unwrap().len();
    let mut handles = vec![];
    for i in 0..count {
        let (url, file, shared, control, failed) = (url.to_string(), file.clone(), shared.clone(), control.clone(), failed.clone());
        handles.push(thread::spawn(move || {
            if let Err(e) = fetch_segment(&url, &file, &shared, i, &control) {
                *failed.lock().unwrap() = Some(e);
            }
        }));
    }
    // Save the plan once a second while the threads work
    while handles.iter().any(|h| !h.is_finished()) {
        thread::sleep(Duration::from_millis(200));
        write_state(state_path, len, &shared.lock().unwrap());
    }
    for h in handles {
        let _ = h.join();
    }
    let segs = shared.lock().unwrap().clone();
    write_state(state_path, len, &segs);
    if let Some(e) = failed.lock().unwrap().take() {
        return Err(e);
    }
    if segs.iter().any(|(_, e, p)| *p <= *e) {
        return Ok(Outcome::Paused);
    }
    let final_path = unique(dir, name);
    fs::rename(part, &final_path).map_err(|e| e.to_string())?;
    let _ = fs::remove_file(state_path);
    Ok(Outcome::Done(final_path))
}

fn fetch_segment(url: &str, file: &File, shared: &Mutex<Vec<(u64, u64, u64)>>, i: usize, control: &Control) -> Result<(), String> {
    let (_start, end, mut pos) = shared.lock().unwrap()[i];
    if pos > end {
        return Ok(());
    }
    let agent = ureq::AgentBuilder::new().timeout_connect(Duration::from_secs(15)).timeout_read(Duration::from_secs(30)).build();
    let resp = agent.get(url).set("Range", &format!("bytes={pos}-{end}")).call().map_err(|e| e.to_string())?;
    if resp.status() != 206 {
        return Err(format!("server ignored the range request (status {})", resp.status()));
    }
    let mut reader = resp.into_reader();
    let mut buf = vec![0u8; CHUNK];
    while pos <= end {
        if control.pause.load(Ordering::Relaxed) {
            return Ok(());
        }
        let want = ((end - pos + 1) as usize).min(CHUNK);
        let got = reader.read(&mut buf[..want]).map_err(|e| e.to_string())?;
        if got == 0 {
            return Err("the server closed the connection early".into());
        }
        file.write_all_at(&buf[..got], pos).map_err(|e| e.to_string())?;
        pos += got as u64;
        shared.lock().unwrap()[i].2 = pos;
        control.done_bytes.fetch_add(got as u64, Ordering::Relaxed);
        control.throttle(got as u64);
    }
    Ok(())
}

fn single(url: &str, dir: &Path, name: &str, part: &Path, control: &Arc<Control>) -> Result<Outcome, String> {
    let resp = ureq::get(url).call().map_err(|e| e.to_string())?;
    if let Some(l) = resp.header("content-length").and_then(|v| v.parse().ok()) {
        control.total_bytes.store(l, Ordering::Relaxed);
    }
    let mut reader = resp.into_reader();
    let mut out = File::create(part).map_err(|e| e.to_string())?;
    let mut buf = vec![0u8; CHUNK];
    loop {
        if control.pause.load(Ordering::Relaxed) {
            let _ = fs::remove_file(part); // this server can't resume: start over next time
            return Ok(Outcome::Paused);
        }
        let got = reader.read(&mut buf).map_err(|e| e.to_string())?;
        if got == 0 {
            break;
        }
        out.write_all(&buf[..got]).map_err(|e| e.to_string())?;
        control.done_bytes.fetch_add(got as u64, Ordering::Relaxed);
        control.throttle(got as u64);
    }
    let final_path = unique(dir, name);
    fs::rename(part, &final_path).map_err(|e| e.to_string())?;
    Ok(Outcome::Done(final_path))
}

// ---------------------------------------------------------------- sorting and schedule

/// The folder a file belongs in, by its ending.
pub fn category(name: &str) -> &'static str {
    let ext = name.rsplit_once('.').map(|(_, e)| e.to_ascii_lowercase()).unwrap_or_default();
    match ext.as_str() {
        "mp4" | "mkv" | "webm" | "avi" | "mov" | "m4v" | "flv" => "Videos",
        "mp3" | "flac" | "ogg" | "opus" | "wav" | "m4a" | "aac" => "Music",
        "jpg" | "jpeg" | "png" | "gif" | "webp" | "svg" | "bmp" | "avif" => "Images",
        "pdf" | "doc" | "docx" | "xls" | "xlsx" | "ppt" | "pptx" | "txt" | "odt" | "epub" => "Documents",
        "zip" | "rar" | "7z" | "tar" | "gz" | "xz" | "zst" | "bz2" => "Archives",
        "iso" | "img" | "exe" | "msi" | "appimage" | "deb" | "rpm" | "pkg" | "dmg" | "apk" | "jar" => "Programs",
        _ => "Other",
    }
}

/// Is the queue allowed to run at this hour? `window` = (from, to) hours; from > to means overnight.
pub fn allowed_now(hour: u32, window: Option<(u32, u32)>) -> bool {
    match window {
        None => true,
        Some((a, b)) if a == b => true,
        Some((a, b)) if a < b => hour >= a && hour < b,
        Some((a, b)) => hour >= a || hour < b,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::{BufRead, BufReader};
    use std::net::TcpListener;

    #[test]
    fn splitting() {
        assert_eq!(split(10, 3), vec![(0, 2), (3, 5), (6, 9)]);
        assert_eq!(split(3, 8).len(), 3);
        assert_eq!(split(1, 8), vec![(0, 0)]);
        let parts = split(1_000_003, 8);
        assert_eq!(parts.iter().map(|(s, e)| e - s + 1).sum::<u64>(), 1_000_003);
    }

    #[test]
    fn names_categories_schedule() {
        assert_eq!(filename_from("https://x.org/a/b/movie.mp4?x=1", None), "movie.mp4");
        assert_eq!(filename_from("https://x.org/", None), "download");
        assert_eq!(filename_from("https://x.org/a", Some("attachment; filename=\"r e.pdf\"")), "r e.pdf");
        assert_eq!(filename_from("https://x.org/a", Some("attachment; filename=\"../../evil\"")), "evil".replace("evil", ".._.._evil").trim_matches('.'));
        assert_eq!(category("a.MKV"), "Videos");
        assert_eq!(category("a.tar"), "Archives");
        assert_eq!(category("a"), "Other");
        assert!(allowed_now(3, Some((23, 6))) && !allowed_now(12, Some((23, 6))));
        assert!(allowed_now(12, None) && allowed_now(9, Some((9, 17))) && !allowed_now(17, Some((9, 17))));
    }

    /// A tiny web server that understands HEAD and Range requests.
    fn serve(data: Vec<u8>, ranges: bool) -> String {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let addr = listener.local_addr().unwrap();
        thread::spawn(move || {
            for stream in listener.incoming() {
                let data = data.clone();
                thread::spawn(move || {
                    let mut stream = stream.unwrap();
                    let mut reader = BufReader::new(stream.try_clone().unwrap());
                    let mut first = String::new();
                    reader.read_line(&mut first).unwrap();
                    let mut range = None;
                    loop {
                        let mut line = String::new();
                        reader.read_line(&mut line).unwrap();
                        if line.trim().is_empty() {
                            break;
                        }
                        if let Some(r) = line.to_ascii_lowercase().strip_prefix("range: bytes=") {
                            let (a, b) = r.trim().split_once('-').unwrap();
                            range = Some((a.parse::<usize>().unwrap(), b.parse::<usize>().unwrap()));
                        }
                    }
                    let head = first.starts_with("HEAD");
                    let ar = if ranges { "Accept-Ranges: bytes\r\n" } else { "" };
                    match range {
                        Some((a, b)) if ranges => {
                            let body = &data[a..=b.min(data.len() - 1)];
                            let _ = write!(stream, "HTTP/1.1 206 Partial Content\r\nContent-Range: bytes {a}-{}/{}\r\nContent-Length: {}\r\nConnection: close\r\n\r\n", a + body.len() - 1, data.len(), body.len());
                            if !head {
                                let _ = stream.write_all(body);
                            }
                        }
                        _ => {
                            let _ = write!(stream, "HTTP/1.1 200 OK\r\n{ar}Content-Length: {}\r\nConnection: close\r\n\r\n", data.len());
                            if !head {
                                let _ = stream.write_all(&data);
                            }
                        }
                    }
                });
            }
        });
        format!("http://{addr}/file.bin")
    }

    fn sample(n: usize) -> Vec<u8> {
        (0..n).map(|i| (i * 7 % 251) as u8).collect()
    }

    fn tmp(tag: &str) -> PathBuf {
        let d = std::env::temp_dir().join(format!("lennox-dl-{tag}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&d);
        d
    }

    #[test]
    fn segmented_download_is_identical() {
        let data = sample(900_001);
        let url = serve(data.clone(), true);
        let dir = tmp("seg");
        let control = Control::new(0);
        let Outcome::Done(path) = run(&url, &dir, 8, &control).unwrap() else { panic!("not done") };
        assert_eq!(fs::read(&path).unwrap(), data);
        assert_eq!(control.done_bytes.load(Ordering::Relaxed), data.len() as u64);
        assert!(!dir.join("file.bin.lennox").exists() && !dir.join("file.bin.part").exists());
        // a second download of the same name does not overwrite
        let Outcome::Done(second) = run(&url, &dir, 4, &Control::new(0)).unwrap() else { panic!() };
        assert_eq!(second.file_name().unwrap(), "file (1).bin");
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn server_without_ranges_still_works() {
        let data = sample(100_000);
        let url = serve(data.clone(), false);
        let dir = tmp("single");
        let Outcome::Done(path) = run(&url, &dir, 8, &Control::new(0)).unwrap() else { panic!() };
        assert_eq!(fs::read(path).unwrap(), data);
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn pause_then_resume_finishes_the_same_file() {
        let data = sample(2_000_000);
        let url = serve(data.clone(), true);
        let dir = tmp("pause");
        let control = Control::new(1_500_000); // slow enough to pause in the middle
        let c2 = control.clone();
        let pauser = thread::spawn(move || {
            thread::sleep(Duration::from_millis(250));
            c2.pause.store(true, Ordering::Relaxed);
        });
        let first = run(&url, &dir, 4, &control).unwrap();
        pauser.join().unwrap();
        assert_eq!(first, Outcome::Paused);
        assert!(dir.join("file.bin.lennox").exists());
        let Outcome::Done(path) = run(&url, &dir, 4, &Control::new(0)).unwrap() else { panic!("not resumed") };
        assert_eq!(fs::read(path).unwrap(), data);
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn speed_limit_slows_it_down() {
        let data = sample(600_000);
        let url = serve(data, true);
        let dir = tmp("limit");
        let start = Instant::now();
        run(&url, &dir, 4, &Control::new(1_000_000)).unwrap();
        assert!(start.elapsed() >= Duration::from_millis(450), "took {:?}", start.elapsed());
        let _ = fs::remove_dir_all(dir);
    }
}
