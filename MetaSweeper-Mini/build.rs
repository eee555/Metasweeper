use std::{env, fs, path::Path, process::Command};

fn python() -> Command {
    if let Ok(exe) = env::var("MINI_PYTHON") {
        return Command::new(exe);
    }
    for candidate in ["python3", "python", "py"] {
        let usable = Command::new(candidate)
            .arg("--version")
            .output()
            .map(|output| output.status.success())
            .unwrap_or(false);
        if usable {
            let mut command = Command::new(candidate);
            if candidate == "py" {
                command.arg("-3");
            }
            return command;
        }
    }
    panic!("Python 3 is required to prepare Mini's shared resources. Set MINI_PYTHON to a Python 3 executable.");
}

fn configure_replay_signer(out: &Path) {
    println!("cargo:rerun-if-env-changed=MINI_REPLAY_SIGNER");
    println!("cargo:rustc-check-cfg=cfg(mini_custom_replay_signer)");
    let Some(path) = env::var_os("MINI_REPLAY_SIGNER") else {
        return;
    };
    let path = Path::new(&path);
    assert!(
        path.is_absolute() && path.is_file(),
        "MINI_REPLAY_SIGNER must point to an existing Rust source file by absolute path: {}",
        path.display()
    );
    let source = path
        .to_str()
        .expect("MINI_REPLAY_SIGNER must be a UTF-8 path");
    println!("cargo:rerun-if-changed={source}");
    println!("cargo:rustc-cfg=mini_custom_replay_signer");
    fs::write(
        out.join("replay_signer_module.rs"),
        format!("#[path = {source:?}]\nmod signer;\n"),
    )
    .expect("could not configure the replay signer");
}

fn main() {
    for path in [
        "obj/ms-toollib/LICENSE",
        "../src/country_name.py",
        "../src/media",
        "resources.py",
    ] {
        println!("cargo:rerun-if-changed={path}");
    }

    #[cfg(windows)]
    {
        let manifest = Path::new(env!("CARGO_MANIFEST_DIR"));
        let icon = manifest.join("../package_tool/cat.ico");
        println!("cargo:rerun-if-changed={}", icon.display());
        let mut resource = winresource::WindowsResource::new();
        resource.set_icon(icon.to_str().expect("icon path is not valid UTF-8"));
        resource
            .compile()
            .expect("could not embed Windows resources");
    }

    let out = env::var_os("OUT_DIR").unwrap();
    let out = Path::new(&out);
    configure_replay_signer(out);
    let status = python()
        .arg("resources.py")
        .arg(out)
        .status()
        .expect("could not start Python to prepare Mini's shared resources");
    assert!(
        status.success(),
        "could not prepare Mini's shared resources"
    );
}
