//! Saved logins, encrypted one by one (ChaCha20-Poly1305). The key lives in a file only you can read
//! (mode 600) next to the vault, so the passwords are not readable from the database file alone.

use chacha20poly1305::aead::{Aead, KeyInit, OsRng};
use chacha20poly1305::{AeadCore, ChaCha20Poly1305, Key, Nonce};
use rusqlite::{params, Connection};
use std::os::unix::fs::PermissionsExt;
use std::path::Path;

pub struct Vault {
    db: Connection,
    cipher: ChaCha20Poly1305,
}

#[derive(Debug, PartialEq)]
pub struct Login {
    pub host: String,
    pub user: String,
    pub password: String,
}

fn load_key(path: &Path) -> Result<Key, String> {
    if let Ok(bytes) = std::fs::read(path) {
        if bytes.len() == 32 {
            return Ok(*Key::from_slice(&bytes));
        }
        return Err("vault.key is damaged".into());
    }
    let key = ChaCha20Poly1305::generate_key(&mut OsRng);
    if let Some(dir) = path.parent() {
        let _ = std::fs::create_dir_all(dir);
    }
    std::fs::write(path, key.as_slice()).map_err(|e| e.to_string())?;
    std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o600)).map_err(|e| e.to_string())?;
    Ok(key)
}

impl Vault {
    pub fn open(db_path: &Path, key_path: &Path) -> Result<Vault, String> {
        let key = load_key(key_path)?;
        let db = Connection::open(db_path).map_err(|e| e.to_string())?;
        db.execute_batch("CREATE TABLE IF NOT EXISTS logins (host TEXT NOT NULL, user TEXT NOT NULL, nonce BLOB NOT NULL, secret BLOB NOT NULL, PRIMARY KEY(host,user));")
            .map_err(|e| e.to_string())?;
        let _ = std::fs::set_permissions(db_path, std::fs::Permissions::from_mode(0o600));
        Ok(Vault { db, cipher: ChaCha20Poly1305::new(&key) })
    }

    pub fn save(&self, host: &str, user: &str, password: &str) -> Result<(), String> {
        let nonce = ChaCha20Poly1305::generate_nonce(&mut OsRng);
        let secret = self.cipher.encrypt(&nonce, password.as_bytes()).map_err(|e| e.to_string())?;
        self.db
            .execute(
                "INSERT INTO logins(host,user,nonce,secret) VALUES(?1,?2,?3,?4) ON CONFLICT(host,user) DO UPDATE SET nonce=excluded.nonce, secret=excluded.secret",
                params![host, user, nonce.as_slice(), secret],
            )
            .map_err(|e| e.to_string())?;
        Ok(())
    }

    /// Logins for a site (and its parent domains: `accounts.example.com` finds `example.com`).
    pub fn for_host(&self, host: &str) -> Result<Vec<Login>, String> {
        let mut out = vec![];
        let mut q = self.db.prepare("SELECT host,user,nonce,secret FROM logins ORDER BY user").map_err(|e| e.to_string())?;
        let rows = q
            .query_map([], |r| Ok((r.get::<_, String>(0)?, r.get::<_, String>(1)?, r.get::<_, Vec<u8>>(2)?, r.get::<_, Vec<u8>>(3)?)))
            .map_err(|e| e.to_string())?;
        for row in rows {
            let (h, user, nonce, secret) = row.map_err(|e| e.to_string())?;
            if host == h || host.ends_with(&format!(".{h}")) {
                let plain = self.cipher.decrypt(Nonce::from_slice(&nonce), secret.as_ref()).map_err(|_| "cannot decrypt (wrong key)".to_string())?;
                out.push(Login { host: h, user, password: String::from_utf8_lossy(&plain).into_owned() });
            }
        }
        Ok(out)
    }

    pub fn hosts(&self) -> Result<Vec<(String, String)>, String> {
        let mut q = self.db.prepare("SELECT host,user FROM logins ORDER BY host,user").map_err(|e| e.to_string())?;
        let rows = q.query_map([], |r| Ok((r.get(0)?, r.get(1)?))).map_err(|e| e.to_string())?;
        rows.collect::<Result<_, _>>().map_err(|e| e.to_string())
    }

    pub fn remove(&self, host: &str, user: &str) -> Result<bool, String> {
        Ok(self.db.execute("DELETE FROM logins WHERE host=?1 AND user=?2", params![host, user]).map_err(|e| e.to_string())? > 0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn dir(tag: &str) -> std::path::PathBuf {
        let d = std::env::temp_dir().join(format!("lennox-vault-{tag}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&d);
        std::fs::create_dir_all(&d).unwrap();
        d
    }
    #[test]
    fn saved_passwords_are_encrypted_and_come_back() {
        let d = dir("a");
        let v = Vault::open(&d.join("v.sqlite"), &d.join("v.key")).unwrap();
        v.save("example.com", "jado", "hunter2-correct").unwrap();
        v.save("example.com", "jado", "changed").unwrap();
        v.save("other.org", "me", "x").unwrap();
        let found = v.for_host("accounts.example.com").unwrap();
        assert_eq!(found, vec![Login { host: "example.com".into(), user: "jado".into(), password: "changed".into() }]);
        assert!(v.for_host("notexample.com").unwrap().is_empty());
        drop(v);
        // the password is not in the file in plain text, and the key is private
        let raw = std::fs::read(d.join("v.sqlite")).unwrap();
        assert!(!raw.windows(7).any(|w| w == b"changed"));
        assert_eq!(std::fs::metadata(d.join("v.key")).unwrap().permissions().mode() & 0o777, 0o600);
        // a different key can't read it
        std::fs::remove_file(d.join("v.key")).unwrap();
        let other = Vault::open(&d.join("v.sqlite"), &d.join("v.key")).unwrap();
        assert!(other.for_host("example.com").is_err());
        assert!(other.remove("example.com", "jado").unwrap());
        let _ = std::fs::remove_dir_all(d);
    }
}
