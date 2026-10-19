"""
SkillStepWorker - runs a skill one step per model turn, then a verification pass.

Small local models do much better with "do step 3 now" than with a five-part procedure in one
go. This worker reuses everything in OllamaChatWorker (streaming, tool approval, tool-call
tolerance, cancellation) and only replaces the outer loop:

    for each '### Step N' of the skill:
        add a user message with that step's questions + Deliver line
        let the model call tools / answer (the normal tool loop)
    then one verification turn: the skill's '## Verification' checklist, with fixes

Every step sees all previous steps and tool results, so the file is read once (in step 1)
and the later steps build on it. OllamaWorker.py itself is not modified.
"""

import json

from PyQt6.QtCore import pyqtSignal

from OllamaPlugin.OllamaWorker import OllamaChatWorker, MAX_TOOL_ROUNDS, _Cancelled


class SkillStepWorker(OllamaChatWorker):
    step_started = pyqtSignal(int, int, str)     # index (1-based), total, title

    def __init__(self, *args, steps=None, checklist=None, skill_name="", require_read=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.require_read = require_read         # stop after step 1 if the model tried to read and could not
        self._read_ok = False
        self._read_error = ""
        self.steps = list(steps or [])           # [(number, title, text), ...]
        self.checklist = list(checklist or [])   # ["30-second summary written", ...]
        self.skill_name = skill_name

    # ------------------------------------------------------------------ prompts

    def _step_prompt(self, index, count, number, title, text):
        first = ("Read the code first with your tools if you have not already "
                 "(read the WHOLE file). " if index == 1 else "")
        return (f"STEP {index} of {count}: {title}\n\n{text}\n\n"
                f"{first}Write ONLY this step. Start with the heading \"### Step {number}: {title}\". "
                f"Base every statement on code you have actually read; say so when you did not "
                f"verify something. Do not repeat earlier steps.")

    def _verify_prompt(self):
        items = "\n".join(f"- {c}" for c in self.checklist)
        return ("VERIFICATION. Check your answer above against this checklist. For each item reply "
                "✔ or ✘ with a few words of reason. If any item is ✘, write only the missing or "
                "corrected part under the heading \"### Fixes\" (do not rewrite everything). Also "
                "mark any claim about the code that you did not actually verify from what you read."
                f"\n\nChecklist:\n{items}")

    # ------------------------------------------------------------------ main loop

    def run(self):
        convo = list(self.messages)
        new_messages = []
        count = len(self.steps)
        total = count + (1 if self.checklist else 0)
        try:
            completed = True
            for i, (number, title, text) in enumerate(self.steps, 1):
                prompt = self._step_prompt(i, count, number, title, text)
                if not self._turn(i, total, title, prompt, convo, new_messages):
                    completed = False
                    break
                if i == 1 and self.require_read and self._read_error and not self._read_ok:
                    # Nothing to explain: do not run five more steps (and a verification) over nothing
                    self.notice.emit("⛔ Stopped after step 1: the target could not be read "
                                     f"({self._read_error}). Give the full path or a longer partial path "
                                     "(for example project/dir/File.py) and try again.")
                    completed = False
                    break
            if completed and self.checklist:
                self._turn(total, total, "Verification", self._verify_prompt(), convo, new_messages)
            self.done.emit(new_messages)
        except _Cancelled:
            self.done.emit(new_messages)
        except Exception as e:
            self.failed.emit(str(e))

    def _turn(self, index, total, title, prompt, convo, new_messages):
        """One user turn with the normal tool loop. Returns False if the user cancelled."""
        self.step_started.emit(index, total, title)
        user = {"role": "user", "content": prompt}
        convo.append(user)
        new_messages.append(user)

        for _ in range(MAX_TOOL_ROUNDS):
            msg, cancelled = self._chat_once(convo)
            if msg["content"] or msg.get("tool_calls"):
                convo.append(msg)
                new_messages.append(msg)
            if cancelled:
                return False
            calls = msg.get("tool_calls") or []
            if not calls:
                return True
            for call in calls:
                fn = call.get("function", {})
                name = fn.get("name", "")
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except ValueError:
                        args = {}
                text, is_error = self._run_tool(name, args)
                if "read" in name.split("__")[-1].lower():          # read_text_file, read_file, ...
                    if is_error:
                        self._read_error = (text.strip().splitlines() or ["error"])[0][:120]
                    else:
                        self._read_ok = True
                tool_msg = {"role": "tool", "tool_name": name, "content": text}
                convo.append(tool_msg)
                new_messages.append(tool_msg)

        self.notice.emit(f"{title}: stopped after {MAX_TOOL_ROUNDS} tool rounds.")
        return True