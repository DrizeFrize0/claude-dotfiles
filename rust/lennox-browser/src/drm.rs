//! Sites that need DRM (Widevine), which WebKitGTK can't play: they open in Zen instead.

const DRM_SITES: [&str; 14] = [
    "netflix.com", "disneyplus.com", "hulu.com", "primevideo.com", "max.com", "hbomax.com", "paramountplus.com",
    "peacocktv.com", "tv.apple.com", "crunchyroll.com", "shahid.net", "osn.com", "watch.amazon.com", "starzplay.com",
];

pub fn needs_drm(url: &str) -> bool {
    let Some(host) = crate::url::host_of(url) else { return false };
    DRM_SITES.iter().any(|d| host == *d || host.ends_with(&format!(".{d}")))
}

#[cfg(test)]
mod tests {
    #[test]
    fn sites() {
        assert!(super::needs_drm("https://www.netflix.com/title/1"));
        assert!(super::needs_drm("https://netflix.com"));
        assert!(!super::needs_drm("https://notnetflix.com"));
        assert!(!super::needs_drm("https://youtube.com/watch"));
    }
}
