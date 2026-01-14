import time

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import IntPrompt, Prompt
from rich.table import Table

from game_logic import RouletteEngine

console = Console()
engine = RouletteEngine()


def show_welcome():
    table = Table(title="🎰 CLI ROULETTE 🎰", style="bold magenta")
    table.add_column("Bet Type", justify="center")
    table.add_column("Payout", justify="center")
    table.add_row("Number (0-36)", "35 to 1")
    table.add_row("Color (Red/Black)", "1 to 1")
    console.print(table)


def main():
    balance = 500
    show_welcome()

    while balance > 0:
        console.print(f"\n[bold cyan]Balance:[/bold cyan] [green]${balance}[/green]")

        # Get Bet
        amount = IntPrompt.ask("Enter bet amount", default=10)
        if amount > balance:
            console.print("[red]Insufficient funds![/red]")
            continue

        bet_type = Prompt.ask(
            "Bet on [bold]number[/bold] or [bold]color[/bold]?",
            choices=["number", "color"],
        )

        if bet_type == "number":
            choice = IntPrompt.ask("Pick a number (0-36)")
        else:
            choice = Prompt.ask("Pick a color", choices=["red", "black"])

        # Spin Animation
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            progress.add_task(description="Spinning the wheel...", total=None)
            time.sleep(2)

        win_num, win_color = engine.spin()

        # Result UI
        color_style = "on green" if win_color == "green" else f"on {win_color}"
        console.print(
            f"\n[bold white {color_style}]  {win_num} {win_color.upper()}  [/bold white {color_style}]\n"
        )

        payout = engine.calculate_payout(bet_type, choice, amount, win_num, win_color)

        if payout > 0:
            balance += payout
            console.print(f"[bold green]WINNER![/bold green] You gained ${payout}")
        else:
            balance += payout
            console.print(f"[bold red]LOSS![/bold red] You lost ${abs(payout)}")

        if balance <= 0:
            console.print("[bold red]Game Over! You're broke.[/bold red] 💸")
            break

        if not Prompt.ask("Play again?", choices=["y", "n"]) == "y":
            break

    console.print(
        f"[bold yellow]Final Cashout: ${balance}. Thanks for playing![/bold yellow]"
    )


if __name__ == "__main__":
    main()
