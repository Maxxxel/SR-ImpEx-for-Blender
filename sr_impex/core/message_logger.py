import bpy


class MessageLogger:
    def __init__(self):
        self.messages = []

    def log(self, message: str, title: str = "Message Box", icon: str = "INFO") -> None:
        if message:
            self.messages.append((title, message, icon))

    def display(self) -> None:
        """Display all accumulated messages and then clear the log."""
        if self.messages:
            # Construct the final message string
            final_message = "\n".join(
                f"{title}: {msg}" for title, msg, _ in self.messages
            )
            # Example: Replace this print with Blender's message operator if needed:
            bpy.ops.my_category.show_messages("INVOKE_DEFAULT", messages=final_message)
            print(final_message)
            self.clear()

    def clear(self) -> None:
        """Clear all logged messages."""
        self.messages = []
