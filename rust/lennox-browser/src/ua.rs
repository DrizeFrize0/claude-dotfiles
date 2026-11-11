//! The browser's name tag. Google refuses to sign you in from what it thinks is an embedded
//! browser (WebKitGTK's default tag says so). Google sites get a Firefox tag, everything else a Safari one.

const SAFARI: &str = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15";
const FIREFOX: &str = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0";

const GOOGLE: [&str; 7] = ["google.com", "youtube.com", "gstatic.com", "googleusercontent.com", "googleapis.com", "gmail.com", "accounts.youtube.com"];

pub fn for_url(url: &str) -> &'static str {
    match crate::url::host_of(url) {
        Some(h) if GOOGLE.iter().any(|g| h == *g || h.ends_with(&format!(".{g}"))) => FIREFOX,
        _ => SAFARI,
    }
}

pub fn default_agent() -> &'static str {
    SAFARI
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn google_gets_firefox() {
        assert!(for_url("https://accounts.google.com/signin").contains("Firefox"));
        assert!(for_url("https://mail.google.com/").contains("Firefox"));
        assert!(for_url("https://www.youtube.com/watch").contains("Firefox"));
        assert!(for_url("https://example.com").contains("Safari") && !for_url("https://example.com").contains("Firefox"));
        assert!(for_url("https://notgoogle.com").contains("Safari"));
        assert!(!for_url("https://accounts.google.com").to_lowercase().contains("webkitgtk"));
    }
}
