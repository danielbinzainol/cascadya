import time
from datetime import datetime, timedelta

import customtkinter as ctk


class PlanificateurTab(ctk.CTkFrame):
    def __init__(self, master, comms, **kwargs):
        super().__init__(master, **kwargs)
        self.comms = comms

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.title = ctk.CTkLabel(
            self,
            text="SteamSwitch Scheduler Commands",
            font=("Arial", 22, "bold"),
        )
        self.title.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        self.form_frame = ctk.CTkFrame(self)
        self.form_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        self.form_frame.grid_columnconfigure((0, 1, 2, 3, 4, 5, 6), weight=1)

        ctk.CTkLabel(self.form_frame, text="Order ID", font=("Arial", 13, "bold")).grid(row=0, column=0, padx=8, pady=(12, 4), sticky="w")
        ctk.CTkLabel(self.form_frame, text="Execute At", font=("Arial", 13, "bold")).grid(row=0, column=1, columnspan=3, padx=8, pady=(12, 4), sticky="w")

        self.entry_order_id = ctk.CTkEntry(self.form_frame)
        self.entry_order_id.grid(row=1, column=0, padx=8, pady=4, sticky="ew")

        self.entry_execute_at = ctk.CTkEntry(self.form_frame)
        self.entry_execute_at.grid(row=1, column=1, columnspan=3, padx=8, pady=4, sticky="ew")

        self.btn_now_plus = ctk.CTkButton(
            self.form_frame,
            text="+60s",
            width=70,
            command=self._set_execute_time_plus_60,
        )
        self.btn_now_plus.grid(row=1, column=4, padx=8, pady=4, sticky="ew")

        self.btn_now_plus300 = ctk.CTkButton(
            self.form_frame,
            text="+5min",
            width=70,
            command=self._set_execute_time_plus_300,
        )
        self.btn_now_plus300.grid(row=1, column=5, padx=8, pady=4, sticky="ew")

        self._build_consigne_headers()

        self.c1_entries = self._build_consigne_row("C1", row=3, defaults=(1, 400, 53))
        self.c2_entries = self._build_consigne_row("C2", row=4, defaults=(2, 1000, 53))
        self.c3_entries = self._build_consigne_row("C3", row=5, defaults=(3, 1000, 53))

        self.actions = ctk.CTkFrame(self.form_frame)
        self.actions.grid(row=6, column=0, columnspan=7, padx=8, pady=(12, 12), sticky="ew")
        self.actions.grid_columnconfigure((0, 1, 2, 3, 4, 5), weight=1)

        self.btn_upsert = ctk.CTkButton(self.actions, text="Upsert Order", command=self.send_upsert)
        self.btn_upsert.grid(row=0, column=0, padx=6, pady=8, sticky="ew")

        self.btn_delete = ctk.CTkButton(self.actions, text="Delete By ID", fg_color="#8B1A1A", hover_color="#6E1414", command=self.send_delete)
        self.btn_delete.grid(row=0, column=1, padx=6, pady=8, sticky="ew")

        self.btn_reset = ctk.CTkButton(self.actions, text="Reset Queue", fg_color="#444444", hover_color="#333333", command=self.send_reset)
        self.btn_reset.grid(row=0, column=2, padx=6, pady=8, sticky="ew")

        self.btn_profile_elec = ctk.CTkButton(self.actions, text="Profile: Elec Priority", command=self.profile_elec_priority)
        self.btn_profile_elec.grid(row=0, column=3, padx=6, pady=8, sticky="ew")

        self.btn_profile_gas = ctk.CTkButton(self.actions, text="Profile: Gas Standby", command=self.profile_gas_priority)
        self.btn_profile_gas.grid(row=0, column=4, padx=6, pady=8, sticky="ew")

        self.btn_profile_degraded = ctk.CTkButton(self.actions, text="Profile: Degraded", command=self.profile_degraded)
        self.btn_profile_degraded.grid(row=0, column=5, padx=6, pady=8, sticky="ew")

        self.log_box = ctk.CTkTextbox(self, height=240, font=("Courier New", 12))
        self.log_box.grid(row=2, column=0, padx=20, pady=(10, 20), sticky="nsew")

        self._set_default_order_id()
        self._set_execute_time_plus_60()
        self.log_message("Scheduler tab ready.")

    def _build_consigne_headers(self):
        ctk.CTkLabel(self.form_frame, text="Consigne", font=("Arial", 12, "bold")).grid(row=2, column=0, padx=8, pady=(10, 4), sticky="w")
        ctk.CTkLabel(self.form_frame, text="A1 (Mode)", font=("Arial", 12, "bold")).grid(row=2, column=1, padx=8, pady=(10, 4), sticky="w")
        ctk.CTkLabel(self.form_frame, text="A2 (Power kW)", font=("Arial", 12, "bold")).grid(row=2, column=2, padx=8, pady=(10, 4), sticky="w")
        ctk.CTkLabel(self.form_frame, text="A3 (Pressure x10)", font=("Arial", 12, "bold")).grid(row=2, column=3, padx=8, pady=(10, 4), sticky="w")

    def _build_consigne_row(self, name, row, defaults):
        ctk.CTkLabel(self.form_frame, text=name, font=("Arial", 12, "bold")).grid(row=row, column=0, padx=8, pady=4, sticky="w")

        entry_a1 = ctk.CTkEntry(self.form_frame)
        entry_a1.insert(0, str(defaults[0]))
        entry_a1.grid(row=row, column=1, padx=8, pady=4, sticky="ew")

        entry_a2 = ctk.CTkEntry(self.form_frame)
        entry_a2.insert(0, str(defaults[1]))
        entry_a2.grid(row=row, column=2, padx=8, pady=4, sticky="ew")

        entry_a3 = ctk.CTkEntry(self.form_frame)
        entry_a3.insert(0, str(defaults[2]))
        entry_a3.grid(row=row, column=3, padx=8, pady=4, sticky="ew")

        return {"a1": entry_a1, "a2": entry_a2, "a3": entry_a3}

    def _set_default_order_id(self):
        self.entry_order_id.delete(0, "end")
        self.entry_order_id.insert(0, str(int(time.time())))

    def _set_execute_time_plus_60(self):
        dt = datetime.now() + timedelta(seconds=60)
        self.entry_execute_at.delete(0, "end")
        self.entry_execute_at.insert(0, dt.strftime("%Y-%m-%d %H:%M:%S"))

    def _set_execute_time_plus_300(self):
        dt = datetime.now() + timedelta(minutes=5)
        self.entry_execute_at.delete(0, "end")
        self.entry_execute_at.insert(0, dt.strftime("%Y-%m-%d %H:%M:%S"))

    def _read_consigne(self, entries):
        return [
            int(entries["a1"].get()),
            int(entries["a2"].get()),
            int(entries["a3"].get()),
        ]

    def _build_upsert_payload(self):
        order_id = int(self.entry_order_id.get())
        execute_at = self.entry_execute_at.get().strip()

        # Validate format early for immediate UI feedback.
        datetime.strptime(execute_at, "%Y-%m-%d %H:%M:%S")

        return {
            "action": "upsert",
            "id": order_id,
            "execute_at": execute_at,
            "c1": self._read_consigne(self.c1_entries),
            "c2": self._read_consigne(self.c2_entries),
            "c3": self._read_consigne(self.c3_entries),
        }

    def send_upsert(self):
        try:
            payload = self._build_upsert_payload()
            self.log_message(f"SEND upsert id={payload['id']} execute_at={payload['execute_at']}")
            self.comms.send_plan_command(payload, label="upsert")
        except Exception as exc:
            self.log_message(f"INPUT ERROR: {exc}")

    def send_delete(self):
        try:
            order_id = int(self.entry_order_id.get())
            payload = {"action": "delete", "id": order_id}
            self.log_message(f"SEND delete id={order_id}")
            self.comms.send_plan_command(payload, label="delete")
        except Exception as exc:
            self.log_message(f"INPUT ERROR: {exc}")

    def send_reset(self):
        payload = {"action": "reset"}
        self.log_message("SEND reset queue")
        self.comms.send_plan_command(payload, label="reset")

    def profile_elec_priority(self):
        self._set_consigne(self.c1_entries, (1, 400, 53))
        self._set_consigne(self.c2_entries, (2, 1000, 53))
        self._set_consigne(self.c3_entries, (3, 1000, 53))
        self.log_message("Loaded profile: Elec Priority")

    def profile_gas_priority(self):
        self._set_consigne(self.c1_entries, (2, 1000, 53))
        self._set_consigne(self.c2_entries, (2, 1000, 52))
        self._set_consigne(self.c3_entries, (3, 1000, 51))
        self.log_message("Loaded profile: Gas Standby")

    def profile_degraded(self):
        self._set_consigne(self.c1_entries, (3, 1000, 50))
        self._set_consigne(self.c2_entries, (3, 1000, 50))
        self._set_consigne(self.c3_entries, (3, 1000, 50))
        self.log_message("Loaded profile: Degraded")

    def _set_consigne(self, entries, values):
        entries["a1"].delete(0, "end")
        entries["a1"].insert(0, str(values[0]))
        entries["a2"].delete(0, "end")
        entries["a2"].insert(0, str(values[1]))
        entries["a3"].delete(0, "end")
        entries["a3"].insert(0, str(values[2]))

    def handle_command_result(self, msg):
        data = msg.get("data", {})
        action = data.get("action", msg.get("label", "command"))
        status = data.get("status", "error")

        if status == "ok":
            details = data.get("status_text", "ok")
            order_id = data.get("order_id")
            suffix = f" id={order_id}" if order_id is not None else ""
            self.log_message(f"ACK {action}{suffix}: {details}")
            if action == "upsert":
                self._set_default_order_id()
        else:
            details = data.get("message", data.get("status_text", "error"))
            self.log_message(f"ACK {action}: ERROR ({details})")

    def log_message(self, text):
        self.log_box.insert("end", f"[{time.strftime('%H:%M:%S')}] {text}\n")
        self.log_box.see("end")
