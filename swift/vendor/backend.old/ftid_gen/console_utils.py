"""
FTID Generator - Rich Console Utilities
Beautiful terminal output using the Rich library.
"""
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.prompt import Prompt, Confirm
    from rich.text import Text
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Global console instance
console = Console() if RICH_AVAILABLE else None


def print_header(title: str, subtitle: str = None):
    """Print a styled header"""
    if RICH_AVAILABLE:
        text = Text(title, style="bold cyan")
        if subtitle:
            text.append(f"\n{subtitle}", style="dim")
        console.print(Panel(text, box=box.DOUBLE, border_style="cyan"))
    else:
        print("\n" + "="*60)
        print(f"  {title}")
        if subtitle:
            print(f"  {subtitle}")
        print("="*60)


def print_menu(options: list, title: str = "Menu"):
    """Print a styled menu"""
    if RICH_AVAILABLE:
        table = Table(show_header=False, box=box.ROUNDED, border_style="dim")
        table.add_column("Key", style="bold yellow", width=4)
        table.add_column("Description", style="white")
        
        for key, description in options:
            table.add_row(key, description)
        
        console.print(Panel(table, title=f"[bold]{title}[/bold]", border_style="blue"))
    else:
        print(f"\n--- {title} ---")
        for key, description in options:
            print(f"  {key}: {description}")


def print_success(message: str):
    """Print a success message"""
    if RICH_AVAILABLE:
        console.print(f"[green]✓[/green] {message}")
    else:
        print(f"✅ {message}")


def print_error(message: str):
    """Print an error message"""
    if RICH_AVAILABLE:
        console.print(f"[red]✗[/red] {message}")
    else:
        print(f"❌ {message}")


def print_warning(message: str):
    """Print a warning message"""
    if RICH_AVAILABLE:
        console.print(f"[yellow]⚠[/yellow] {message}")
    else:
        print(f"⚠️ {message}")


def print_info(message: str):
    """Print an info message"""
    if RICH_AVAILABLE:
        console.print(f"[blue]ℹ[/blue] {message}")
    else:
        print(f"ℹ️ {message}")


def get_input(prompt: str, default: str = None) -> str:
    """Get user input with optional default"""
    if RICH_AVAILABLE and default:
        return Prompt.ask(prompt, default=default)
    elif default:
        result = input(f"{prompt} [{default}]: ").strip()
        return result if result else default
    else:
        return input(f"{prompt}: ").strip()


def confirm(prompt: str, default: bool = False) -> bool:
    """Get yes/no confirmation"""
    if RICH_AVAILABLE:
        return Confirm.ask(prompt, default=default)
    else:
        response = input(f"{prompt} ({'Y/n' if default else 'y/N'}): ").strip().lower()
        if not response:
            return default
        return response in ('y', 'yes')


def show_spinner(message: str):
    """Show a spinner for long operations"""
    if RICH_AVAILABLE:
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True
        )
    return None


def print_label_info(info: dict):
    """Print label information in a table"""
    if RICH_AVAILABLE:
        table = Table(show_header=False, box=box.SIMPLE)
        table.add_column("Field", style="bold")
        table.add_column("Value", style="cyan")
        
        fields = [
            ("Sender", info.get('sender', '')),
            ("Address", info.get('sender_address', '')),
            ("City/State/ZIP", info.get('sender_2nd_line', '')),
            ("Receiver", info.get('receiver', '')),
            ("Address", info.get('receiver_address', '')),
            ("City/State/ZIP", info.get('receiver_2nd_line', '')),
            ("Tracking", info.get('tracking_number', '')),
        ]
        
        for field, value in fields:
            if value:
                table.add_row(field, str(value))
        
        console.print(Panel(table, title="[bold green]Label Generated[/bold green]"))
    else:
        print("\n=== Label Info ===")
        for key, value in info.items():
            if key not in ['tracking_bar']:
                print(f"  {key}: {value}")
