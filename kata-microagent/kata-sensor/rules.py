RULES = [
    {
        "event_type": "unexpected_shell",
        "severity": "high",
        "process_names": {"sh", "bash", "ash", "dash", "zsh"},
        "cmdline_patterns": [],
        "reason": "shell execution inside application workload",
    },
    {
        "event_type": "shadow_file_access",
        "severity": "high",
        "process_names": {"cat", "tail", "head", "less", "more"},
        "cmdline_patterns": ["/etc/shadow"],
        "reason": "attempt to read sensitive system file",
    },
    {
        "event_type": "aws_credential_discovery",
        "severity": "medium",
        "process_names": {"find"},
        "cmdline_patterns": [".aws/credentials", ".AWS/credentials"],
        "reason": "attempt to discover AWS credential file",
    },
    {
        "event_type": "nc_execution",
        "severity": "high",
        "process_names": {"nc", "netcat", "ncat", "socat"},
        "cmdline_patterns": ["-e", "-c", "--exec", "--sh-exec", "--lua-exec"],
        "reason": "network utility used for remote code execution inside workload",
    },
    {
        "event_type": "network_download_utility",
        "severity": "medium",
        "process_names": {"curl", "wget"},
        "cmdline_patterns": ["http", "https"],
        "reason": "unexpected download or external network access via transfer utility",
    },
    {
        "event_type": "package_manager_execution",
        "severity": "high",
        "process_names": {"apt", "apt-get", "apk", "yum", "dnf", "rpm", "dpkg"},
        "cmdline_patterns": ["install", "add"],
        "reason": "package manager used to install new software inside running workload",
    },
]