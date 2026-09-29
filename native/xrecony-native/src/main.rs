use std::collections::VecDeque;
use std::env;
use std::fs::{self, DirEntry};
use std::io::{self, BufWriter, Write};
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

fn escaped(value: &str) -> String {
    let mut out = String::with_capacity(value.len() + 8);
    for ch in value.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if c.is_control() => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out
}

fn nanos(value: io::Result<SystemTime>) -> u128 {
    value.ok().and_then(|v| v.duration_since(UNIX_EPOCH).ok()).map(|v| v.as_nanos()).unwrap_or(0)
}

fn emit(out: &mut BufWriter<io::StdoutLock<'_>>, root: &Path, entry: DirEntry) -> io::Result<Option<PathBuf>> {
    let path = entry.path();
    let rel = path.strip_prefix(root).unwrap_or(&path).to_string_lossy();
    let metadata = fs::symlink_metadata(&path)?;
    let file_type = metadata.file_type();
    let kind = if file_type.is_symlink() { "link" } else if file_type.is_dir() { "directory" } else { "file" };
    let size = if file_type.is_file() { metadata.len() } else { 0 };
    writeln!(
        out,
        "{{\"rel_path\":\"{}\",\"abs_path\":\"{}\",\"name\":\"{}\",\"kind\":\"{}\",\"size\":{},\"modified_ns\":{},\"created_ns\":{}}}",
        escaped(&rel),
        escaped(&path.to_string_lossy()),
        escaped(&entry.file_name().to_string_lossy()),
        kind,
        size,
        nanos(metadata.modified()),
        nanos(metadata.created())
    )?;
    Ok(if file_type.is_dir() && !file_type.is_symlink() { Some(path) } else { None })
}

fn main() -> io::Result<()> {
    let source = env::args_os().nth(1).map(PathBuf::from).ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "usage: xrecony-native <source>"))?;
    let root = source.canonicalize()?;
    let stdout = io::stdout();
    let mut out = BufWriter::with_capacity(1024 * 1024, stdout.lock());
    let mut queue = VecDeque::from([root.clone()]);
    while let Some(folder) = queue.pop_front() {
        for item in fs::read_dir(folder)? {
            match item.and_then(|entry| emit(&mut out, &root, entry)) {
                Ok(Some(child)) => queue.push_back(child),
                Ok(None) => {}
                Err(error) => eprintln!("xrecony-native: {error}"),
            }
        }
    }
    out.flush()
}
