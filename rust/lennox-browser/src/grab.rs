//! Video grabber: asks yt-dlp to download the video on a page, into your Videos folder.

use std::path::Path;

pub fn args(page: &str, videos_dir: &Path) -> Vec<String> {
    vec![
        "--no-playlist".into(),
        "-P".into(),
        videos_dir.display().to_string(),
        "-o".into(),
        "%(title).150B [%(id)s].%(ext)s".into(),
        "--concurrent-fragments".into(),
        "8".into(),
        "--merge-output-format".into(),
        "mp4".into(),
        page.into(),
    ]
}

/// Arguments to float a page's video in a small always-on-top player (mpv).
pub fn pip_args(page: &str) -> Vec<String> {
    vec![
        "--ontop".into(),
        "--no-border".into(),
        "--autofit=480x270".into(),
        "--geometry=100%:100%".into(),
        "--title=lennox-pip".into(),
        "--x11-name=lennox-pip".into(),
        "--wayland-app-id=lennox-pip".into(),
        "--keep-open=no".into(),
        page.into(),
    ]
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn arguments() {
        let a = args("https://v.test/watch?x=1", Path::new("/home/u/Downloads/Videos"));
        assert_eq!(a.last().unwrap(), "https://v.test/watch?x=1");
        assert!(a.windows(2).any(|w| w == ["-P", "/home/u/Downloads/Videos"]));
        assert!(pip_args("u").contains(&"--wayland-app-id=lennox-pip".to_string()));
    }
}
