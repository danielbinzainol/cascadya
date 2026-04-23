from __future__ import annotations

import os

from backend.prompts import InteractivePrompt

WSL_DISTRO = os.environ.get("CASCADYA_WSL_DISTRO", "ubuntu")

SSH_PASSWORD = os.environ.get("CASCADYA_SSH_PASSWORD", "admin")
SUDO_PASSWORD = os.environ.get("CASCADYA_SUDO_PASSWORD", SSH_PASSWORD)
WSL_SUDO_PASSWORD = os.environ.get("CASCADYA_WSL_SUDO_PASSWORD", SUDO_PASSWORD)

PASSWORD_PROMPT_PATTERN = r"password.*:\s*$"
HOST_KEY_PROMPT_PATTERN = r"are you sure you want to continue connecting.*\?\s*$"
SSH_KEY_PASSPHRASE_PROMPT_PATTERN = r"enter passphrase for key.*:\s*$"

REMOTE_UNLOCK_ANSIBLE_PATH = os.environ.get(
    "CASCADYA_REMOTE_UNLOCK_ANSIBLE_PATH",
    "~/git/cascadya-project/cascadya-edge-os-images/ansible",
)
REMOTE_UNLOCK_IPC_INVENTORY = os.environ.get(
    "CASCADYA_REMOTE_UNLOCK_IPC_INVENTORY",
    "inventory-remote-unlock.ini",
)
REMOTE_UNLOCK_BROKER_INVENTORY = os.environ.get(
    "CASCADYA_REMOTE_UNLOCK_BROKER_INVENTORY",
    "inventory-remote-unlock-broker.ini",
)
REMOTE_UNLOCK_DEVICE_ID = os.environ.get("CASCADYA_REMOTE_UNLOCK_DEVICE_ID", "cascadya")
REMOTE_UNLOCK_WIREGUARD_KEY_PATH = os.environ.get(
    "CASCADYA_REMOTE_UNLOCK_WG_KEY_PATH",
    "~/wg-remote-unlock/cascadya/ipc.key",
)
REMOTE_UNLOCK_VAULT_SECRET_VALUE = os.environ.get(
    "CASCADYA_REMOTE_UNLOCK_VAULT_SECRET_VALUE",
    SSH_PASSWORD,
)
REMOTE_UNLOCK_BROKER_VAULT_TOKEN_ENV_VAR = "REMOTE_UNLOCK_BROKER_VAULT_TOKEN"
REMOTE_UNLOCK_BROKER_SSH_KEY_PASSPHRASE = os.environ.get(
    "CASCADYA_BROKER_SSH_KEY_PASSPHRASE",
    "",
)

INDUSTRIAL_PC_TARGET = os.environ.get(
    "CASCADYA_REMOTE_UNLOCK_IPC_TARGET",
    "cascadya@192.168.10.109",
)

SYNC_WARNING_EXIT_CODES = frozenset({0, 23, 24})

INDUSTRIAL_PC_HOST_KEY_CONFIRMATION_PROMPTS = (
    InteractivePrompt(
        pattern=HOST_KEY_PROMPT_PATTERN,
        response="yes",
        description="industrial pc key confirmation",
    ),
)

INDUSTRIAL_PC_LOGIN_PASSWORD_PROMPTS = (
    InteractivePrompt(
        pattern=PASSWORD_PROMPT_PATTERN,
        response=SSH_PASSWORD,
        description="industrial pc password",
    ),
)

REMOTE_SUDO_PASSWORD_PROMPT = (
    InteractivePrompt(
        pattern=PASSWORD_PROMPT_PATTERN,
        response=SUDO_PASSWORD,
        description="remote sudo password",
    ),
)

ANSIBLE_IPC_PASSWORD_PROMPTS = (
    InteractivePrompt(
        pattern=r"ssh password:\s*$",
        response=SSH_PASSWORD,
        description="ansible ssh password",
    ),
    InteractivePrompt(
        pattern=r"become password.*:\s*$",
        response=SUDO_PASSWORD,
        description="ansible become password",
    ),
)

REMOTE_UNLOCK_BROKER_SSH_KEY_PASSPHRASE_PROMPTS = (
    ()
    if not REMOTE_UNLOCK_BROKER_SSH_KEY_PASSPHRASE
    else (
        InteractivePrompt(
            pattern=SSH_KEY_PASSPHRASE_PROMPT_PATTERN,
            response=REMOTE_UNLOCK_BROKER_SSH_KEY_PASSPHRASE,
            description="broker ssh key passphrase",
        ),
    )
)
