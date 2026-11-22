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
        "../win/Build/build_resources.py",
        "../win/Configuration/UiText.cs",
        "../win/Game/ReplayChecksum.cs",
        "../win/UI/ClassicSprites.cs",
        "../obj/ms-toollib/LICENSE",
        "../../src/country_name.py",
        "../../src/media",
        "resources.py",
    ] {
        println!("cargo:rerun-if-changed={path}");
    }
    let out = env::var_os("OUT_DIR").unwrap();
    let status = python()
        .arg("resources.py")
        .arg(Path::new(&out))
        .status()
        .expect("could not start Python to prepare Mini's shared resources");
    assert!(status.success(), "could not prepare Mini's shared resources");
}
