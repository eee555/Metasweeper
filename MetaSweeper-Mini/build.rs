use std::{env, path::Path, process::Command};

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
        resource.compile().expect("could not embed Windows resources");
    }

    let out = env::var_os("OUT_DIR").unwrap();
    let status = python()
        .arg("resources.py")
        .arg(Path::new(&out))
        .status()
        .expect("could not start Python to prepare Mini's shared resources");
    assert!(status.success(), "could not prepare Mini's shared resources");
}
