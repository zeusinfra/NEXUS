use pyo3::prelude::*;
use std::collections::HashSet;

#[pyclass]
pub struct CommandPolicyRust {
    read_commands: HashSet<String>,
    write_commands: HashSet<String>,
    blocked_commands: HashSet<String>,
    shell_control: HashSet<char>,
}

#[pymethods]
impl CommandPolicyRust {
    #[new]
    pub fn new() -> Self {
        let read = ["ls", "pwd", "echo", "cat", "sed", "rg", "find", "wc", "git", "python3", "node", "npm", "cargo"]
            .iter().map(|s| s.to_string()).collect();
        let write = ["cp", "mv", "mkdir", "touch", "chmod", "chown", "git"]
            .iter().map(|s| s.to_string()).collect();
        let blocked = ["mkfs", "dd", "shutdown", "reboot", "poweroff", "halt", "passwd", "usermod", "useradd", "groupadd", "visudo", "mount", "umount", "rm"]
            .iter().map(|s| s.to_string()).collect();
        let shell = ['|', '&', ';', '>', '<', '$', '`'];

        CommandPolicyRust {
            read_commands: read,
            write_commands: write,
            blocked_commands: blocked,
            shell_control: shell.iter().cloned().collect(),
        }
    }

    pub fn validate_command(&self, cmd: String, tokens: Vec<String>, confirmed: bool) -> PyResult<(bool, String)> {
        if tokens.is_empty() {
            return Ok((false, "Comando vazio".to_string()));
        }

        let exe = &tokens[0];

        // 1. Check blocked commands
        if self.blocked_commands.contains(exe) {
            return Ok((false, format!("Comando bloqueado por segurança: {}", exe)));
        }

        // 2. Check shell control tokens
        if cmd.chars().any(|c| self.shell_control.contains(&c)) {
            return Ok((false, "Encadeamento ou redirecionamento de shell bloqueado".to_string()));
        }

        // 3. Check write commands confirmation
        if self.write_commands.contains(exe) && !confirmed {
            return Ok((false, format!("Comando de escrita '{}' requer confirmação explícita", exe)));
        }

        Ok((true, "Permitido".to_string()))
    }

    pub fn is_risky(&self, tokens: Vec<String>) -> bool {
        if tokens.is_empty() { return false; }
        let exe = &tokens[0];
        self.write_commands.contains(exe) || exe == "python3" || exe == "node" || exe == "cargo"
    }
}

#[pymodule]
fn zeus_policy(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<CommandPolicyRust>()?;
    Ok(())
}
