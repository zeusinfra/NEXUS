#![allow(non_local_definitions)]

use pyo3::prelude::*;
use std::collections::{HashMap, HashSet};
use std::path::Path;

#[pyclass]
pub struct CommandPolicyRust {
    write_commands: HashSet<String>,
    blocked_commands: HashSet<String>,
    confirmation_only_commands: HashSet<String>,
    shell_control_tokens: Vec<String>,
    risky_interpreter_flags: HashMap<String, HashSet<String>>,
    safe_interpreter_args: HashMap<String, HashSet<String>>,
    risky_package_subcommands: HashMap<String, HashSet<String>>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct Decision {
    exe: String,
    category: String,
    requires_confirmation: bool,
}

#[pymethods]
impl CommandPolicyRust {
    #[new]
    pub fn new() -> Self {
        CommandPolicyRust {
            write_commands: set(&[
                "cp",
                "mv",
                "mkdir",
                "touch",
                "chmod",
                "chown",
                "git",
                "rm",
                "apt",
                "pip",
                "pip3",
                "npm",
                "cargo",
                "systemctl",
            ]),
            confirmation_only_commands: set(&[
                "python3",
                "python",
                "node",
                "npm",
                "npx",
                "cargo",
                "rm",
                "apt",
                "systemctl",
            ]),
            blocked_commands: set(&[
                "rm", "mkfs", "dd", "shutdown", "reboot", "poweroff", "halt", "passwd", "usermod",
                "useradd", "userdel", "groupadd", "groupmod", "groupdel", "visudo", "chpasswd",
                "mount", "umount",
            ]),
            shell_control_tokens: vec![
                "|".to_string(),
                "&&".to_string(),
                "||".to_string(),
                ";".to_string(),
                ">".to_string(),
                ">>".to_string(),
                "<".to_string(),
                "$(".to_string(),
                "`".to_string(),
            ],
            risky_interpreter_flags: map_sets(&[
                ("python", &["-c", "-m"][..]),
                ("python3", &["-c", "-m"][..]),
                (
                    "node",
                    &["-e", "--eval", "-p", "--print", "-r", "--require"][..],
                ),
            ]),
            safe_interpreter_args: map_sets(&[
                ("python", &["--version", "-V"][..]),
                ("python3", &["--version", "-V"][..]),
                ("node", &["--version", "-v"][..]),
            ]),
            risky_package_subcommands: map_sets(&[
                (
                    "npm",
                    &[
                        "exec",
                        "explore",
                        "install",
                        "i",
                        "link",
                        "rebuild",
                        "run",
                        "run-script",
                        "start",
                        "test",
                    ][..],
                ),
                ("npx", &["*"][..]),
                (
                    "cargo",
                    &[
                        "bench", "build", "clippy", "fix", "install", "publish", "run", "test",
                    ][..],
                ),
                (
                    "apt",
                    &[
                        "install",
                        "remove",
                        "purge",
                        "upgrade",
                        "dist-upgrade",
                        "autoremove",
                        "full-upgrade",
                    ][..],
                ),
                (
                    "systemctl",
                    &[
                        "start", "stop", "restart", "enable", "disable", "mask", "unmask", "reload",
                    ][..],
                ),
            ]),
        }
    }

    pub fn validate_command(
        &self,
        cmd: String,
        tokens: Vec<String>,
        confirmed: bool,
    ) -> PyResult<(bool, String)> {
        Ok(self.validate(&cmd, &tokens, confirmed))
    }

    pub fn classify_command(&self, tokens: Vec<String>) -> PyResult<(String, String, bool)> {
        let decision = self.classify(&tokens);
        Ok((
            decision.exe,
            decision.category,
            decision.requires_confirmation,
        ))
    }

    pub fn is_risky(&self, tokens: Vec<String>) -> bool {
        self.classify(&tokens).requires_confirmation
    }
}

impl CommandPolicyRust {
    fn validate(&self, cmd: &str, tokens: &[String], confirmed: bool) -> (bool, String) {
        if tokens.is_empty() {
            return (false, "Comando vazio".to_string());
        }

        let decision = self.classify(tokens);
        let autonomy = autonomy_level();

        if self.blocked_commands.contains(&decision.exe) {
            return (
                false,
                format!("Comando bloqueado por segurança: {}", decision.exe),
            );
        }

        if autonomy != "FULL" && self.contains_shell_control(cmd) {
            return (
                false,
                "Encadeamento/redirecionamento de shell bloqueado em cmd_control.".to_string(),
            );
        }

        if autonomy != "FULL" && !configured_allowlist().contains(&decision.exe) {
            return (
                false,
                format!("Comando fora da allowlist: {}", decision.exe),
            );
        }

        if autonomy != "FULL" && decision.requires_confirmation && !confirmed {
            return (
                false,
                format!("Comando requer confirmação explícita: {}", decision.exe),
            );
        }

        (true, "Permitido".to_string())
    }

    fn classify(&self, tokens: &[String]) -> Decision {
        let exe = tokens.first().map(|t| basename(t)).unwrap_or_default();
        let autonomy = autonomy_level();

        if autonomy == "FULL" {
            return Decision {
                exe,
                category: "autonomous".to_string(),
                requires_confirmation: false,
            };
        }

        if self.write_commands.contains(&exe) {
            return Decision {
                exe,
                category: "write".to_string(),
                requires_confirmation: true,
            };
        }

        if self.requires_confirmation_for_args(&exe, &tokens[1..]) {
            return Decision {
                exe,
                category: "exec".to_string(),
                requires_confirmation: true,
            };
        }

        Decision {
            exe,
            category: "read".to_string(),
            requires_confirmation: false,
        }
    }

    fn requires_confirmation_for_args(&self, exe: &str, args: &[String]) -> bool {
        if let Some(risky_flags) = self.risky_interpreter_flags.get(exe) {
            let safe_args = self.safe_interpreter_args.get(exe);
            return !args.is_empty()
                && (args.iter().any(|arg| risky_flags.contains(arg))
                    || args
                        .iter()
                        .any(|arg| safe_args.map(|safe| !safe.contains(arg)).unwrap_or(true)));
        }

        if let Some(risky_subcommands) = self.risky_package_subcommands.get(exe) {
            if risky_subcommands.contains("*") {
                return true;
            }
            let first_arg = args
                .iter()
                .find(|arg| !arg.starts_with('-'))
                .map(String::as_str)
                .unwrap_or("");
            return risky_subcommands.contains(first_arg);
        }

        self.confirmation_only_commands.contains(exe) && !args.is_empty()
    }

    fn contains_shell_control(&self, cmd: &str) -> bool {
        self.shell_control_tokens
            .iter()
            .any(|token| cmd.contains(token))
    }
}

impl Default for CommandPolicyRust {
    fn default() -> Self {
        Self::new()
    }
}

fn set(items: &[&str]) -> HashSet<String> {
    items.iter().map(|item| item.to_string()).collect()
}

fn map_sets(items: &[(&str, &[&str])]) -> HashMap<String, HashSet<String>> {
    items
        .iter()
        .map(|(key, values)| (key.to_string(), set(values)))
        .collect()
}

fn basename(token: &str) -> String {
    Path::new(token)
        .file_name()
        .and_then(|name| name.to_str())
        .unwrap_or(token)
        .to_string()
}

fn autonomy_level() -> String {
    std::env::var("ZEUS_AUTONOMY_LEVEL")
        .unwrap_or_else(|_| "GUARDED".to_string())
        .to_uppercase()
}

fn configured_allowlist() -> HashSet<String> {
    std::env::var("ZEUS_CMD_ALLOWLIST")
        .unwrap_or_else(|_| {
            "ls,pwd,echo,cat,sed,rg,find,wc,python3,node,npm,cargo,git,systemctl,apt,pip,pip3,df,free,uptime,ip,ss,top,htop"
                .to_string()
        })
        .split(',')
        .map(str::trim)
        .filter(|item| !item.is_empty())
        .map(str::to_string)
        .collect()
}

#[pymodule]
fn zeus_policy(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<CommandPolicyRust>()?;
    Ok(())
}

#[cfg(test)]
#[allow(clippy::useless_vec)]
mod tests {
    use super::*;
    use std::sync::Mutex;

    static ENV_LOCK: Mutex<()> = Mutex::new(());

    fn with_env<F: FnOnce()>(autonomy: &str, allowlist: &str, f: F) {
        let _guard = ENV_LOCK.lock().unwrap();
        std::env::set_var("ZEUS_AUTONOMY_LEVEL", autonomy);
        std::env::set_var("ZEUS_CMD_ALLOWLIST", allowlist);
        f();
        std::env::remove_var("ZEUS_AUTONOMY_LEVEL");
        std::env::remove_var("ZEUS_CMD_ALLOWLIST");
    }

    #[test]
    fn allows_safe_read_command() {
        with_env("GUARDED", "python3", || {
            let policy = CommandPolicyRust::new();
            let (ok, reason) = policy.validate(
                "python3 --version",
                &vec!["python3".into(), "--version".into()],
                false,
            );
            assert!(ok, "{reason}");
            let decision = policy.classify(&vec!["python3".into(), "--version".into()]);
            assert_eq!(decision.category, "read");
        });
    }

    #[test]
    fn rejects_outside_allowlist() {
        with_env("GUARDED", "python3", || {
            let policy = CommandPolicyRust::new();
            let (ok, reason) =
                policy.validate("git status", &vec!["git".into(), "status".into()], false);
            assert!(!ok);
            assert!(reason.contains("allowlist"));
        });
    }

    #[test]
    fn blocks_absolute_danger_even_in_full() {
        with_env("FULL", "rm", || {
            let policy = CommandPolicyRust::new();
            let (ok, reason) =
                policy.validate("rm something", &vec!["rm".into(), "something".into()], true);
            assert!(!ok);
            assert!(reason.contains("bloqueado"));
        });
    }

    #[test]
    fn rejects_shell_control_in_guarded_but_not_full() {
        with_env("GUARDED", "python3", || {
            let policy = CommandPolicyRust::new();
            let (ok, _) = policy.validate(
                "python3 --version && git status",
                &vec![
                    "python3".into(),
                    "--version".into(),
                    "&&".into(),
                    "git".into(),
                    "status".into(),
                ],
                false,
            );
            assert!(!ok);
        });

        with_env("FULL", "python3", || {
            let policy = CommandPolicyRust::new();
            let (ok, reason) = policy.validate(
                "python3 --version && git status",
                &vec![
                    "python3".into(),
                    "--version".into(),
                    "&&".into(),
                    "git".into(),
                    "status".into(),
                ],
                false,
            );
            assert!(ok, "{reason}");
        });
    }

    #[test]
    fn interpreter_flags_require_confirmation() {
        with_env("GUARDED", "python3,node", || {
            let policy = CommandPolicyRust::new();
            let (ok, reason) = policy.validate(
                "python3 -c print(1)",
                &vec!["python3".into(), "-c".into(), "print(1)".into()],
                false,
            );
            assert!(!ok);
            assert!(reason.contains("confirmação"));

            let (ok, reason) = policy.validate(
                "python3 -c print(1)",
                &vec!["python3".into(), "-c".into(), "print(1)".into()],
                true,
            );
            assert!(ok, "{reason}");
        });
    }
}
