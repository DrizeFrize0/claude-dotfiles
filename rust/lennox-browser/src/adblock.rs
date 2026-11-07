//! Blocks ads and trackers by domain: a host and all its subdomains.

use std::collections::HashSet;

const BUILT_IN: &str = "doubleclick.net googlesyndication.com googleadservices.com adservice.google.com \
google-analytics.com googletagmanager.com googletagservices.com adnxs.com adsrvr.org taboola.com outbrain.com \
criteo.com criteo.net scorecardresearch.com quantserve.com facebook.net connect.facebook.net hotjar.com \
mixpanel.com segment.io amplitude.com ads-twitter.com analytics.twitter.com pubmatic.com rubiconproject.com \
openx.net casalemedia.com moatads.com yieldmo.com 33across.com adform.net advertising.com bidswitch.net \
smartadserver.com tiktokcdn-analytics.com analytics.tiktok.com ads.yahoo.com popads.net propellerads.com \
exoclick.com juicyads.com trafficjunky.com";

#[derive(Default)]
pub struct Blocker {
    domains: HashSet<String>,
}

impl Blocker {
    pub fn built_in() -> Self {
        let mut b = Blocker::default();
        b.add_words(BUILT_IN);
        b
    }

    fn add_words(&mut self, text: &str) {
        for w in text.split_whitespace() {
            self.domains.insert(w.to_ascii_lowercase());
        }
    }

    /// Adds a hosts-style list ("0.0.0.0 ads.example.com") or one domain per line; `#` starts a comment.
    pub fn add_list(&mut self, text: &str) {
        for line in text.lines() {
            let line = line.split('#').next().unwrap_or("").trim();
            let mut parts = line.split_whitespace();
            let first = parts.next();
            let domain = match first {
                Some("0.0.0.0") | Some("127.0.0.1") => parts.next(),
                other => other,
            };
            if let Some(d) = domain {
                if d.contains('.') && d != "localhost" {
                    self.domains.insert(d.to_ascii_lowercase());
                }
            }
        }
    }

    pub fn len(&self) -> usize {
        self.domains.len()
    }

    pub fn is_empty(&self) -> bool {
        self.domains.is_empty()
    }

    /// Is this host, or any parent of it, on the list? `sub.ads.example.com` is blocked by `ads.example.com`.
    pub fn blocks_host(&self, host: &str) -> bool {
        let host = host.trim_end_matches('.').to_ascii_lowercase();
        let mut rest = host.as_str();
        loop {
            if self.domains.contains(rest) {
                return true;
            }
            match rest.split_once('.') {
                Some((_, parent)) if parent.contains('.') => rest = parent,
                _ => return false,
            }
        }
    }

    /// WebKit content-blocker rules (JSON) for the whole list: how the window blocks ads inside pages.
    pub fn content_rules_json(&self) -> String {
        let mut names: Vec<&String> = self.domains.iter().collect();
        names.sort();
        let rules: Vec<String> = names
            .iter()
            .map(|d| {
                let escaped = d.replace('.', "\\\\.");
                format!(r#"{{"trigger":{{"url-filter":"^https?://([^/:]+\\.)?{escaped}[:/]"}},"action":{{"type":"block"}}}}"#)
            })
            .collect();
        format!("[{}]", rules.join(","))
    }

    pub fn blocks_url(&self, url: &str) -> bool {
        crate::url::host_of(url).map(|h| self.blocks_host(&h)).unwrap_or(false)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn content_rules_are_valid_json_that_matches() {
        let mut b = Blocker::default();
        b.add_list("ads.example.com\ntracker.test");
        let json = b.content_rules_json();
        assert_eq!(json, r#"[{"trigger":{"url-filter":"^https?://([^/:]+\\.)?ads\\.example\\.com[:/]"},"action":{"type":"block"}},{"trigger":{"url-filter":"^https?://([^/:]+\\.)?tracker\\.test[:/]"},"action":{"type":"block"}}]"#);
    }

    #[test]
    fn subdomains_and_lists() {
        let mut b = Blocker::built_in();
        assert!(b.blocks_url("https://stats.g.doubleclick.net/x"));
        assert!(b.blocks_host("DoubleClick.net."));
        assert!(!b.blocks_host("example.com"));
        assert!(!b.blocks_host("notdoubleclick.net"));
        b.add_list("# comment\n0.0.0.0 tracker.test\nads.other.org\n127.0.0.1 localhost\n");
        assert!(b.blocks_url("http://x.tracker.test/a.js"));
        assert!(b.blocks_host("ads.other.org"));
        assert!(!b.blocks_host("localhost"));
        assert!(!b.blocks_host("org"));
    }
}
