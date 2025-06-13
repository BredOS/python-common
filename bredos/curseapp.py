import time
import curses
import textwrap

stdscr = None
NOCONFIRM = False
DRYRUN = False
APP_NAME = "BredOS"
enabled = False


def message(text: list, label: str = APP_NAME, prompt: bool = True) -> None:
    if stdscr is None:
        for line in text:
            print(line)
        return

    while True:
        try:
            text = [subline for line in text for subline in line.split("\n")]
            maxy, maxx = stdscr.getmaxyx()
            content_height = maxy - 5  # borders + label + prompt
            text = [
                wrapped
                for subline in text
                for wrapped in (textwrap.wrap(subline, maxx) or [""])
            ]
            scroll = 0

            while True:
                stdscr.clear()
                draw_border()
                stdscr.addstr(
                    1,
                    2,
                    label + (" (DRYRUN)" if DRYRUN else ""),
                    curses.A_BOLD | curses.A_UNDERLINE,
                )

                visible_lines = text[scroll : scroll + content_height]
                for i, line in enumerate(visible_lines):
                    stdscr.addstr(3 + i, 2, line[: maxx - 4])

                if not prompt:
                    stdscr.refresh()
                    return

                stdscr.attron(curses.A_REVERSE)
                stdscr.addstr(
                    maxy - 2,
                    2,
                    (" SCROLL DOWN --" if scroll + content_height < len(text) else "")
                    + " Press Enter to continue ",
                )
                stdscr.attroff(curses.A_REVERSE)
                stdscr.refresh()

                key = stdscr.getch()
                if key in (ord("\n"), curses.KEY_ENTER):
                    break
                elif key in (curses.KEY_DOWN, ord("s"), ord("S")):
                    if scroll + content_height < len(text):
                        scroll += 1
                elif key in (curses.KEY_UP, ord("w"), ord("W")):
                    if scroll > 0:
                        scroll -= 1

            wait_clear()
            return
        except KeyboardInterrupt:
            pass
        except:
            pass


def confirm(text: list, label: str = APP_NAME) -> bool:
    global NOCONFIRM
    if NOCONFIRM:
        return True
    while True:
        try:
            if stdscr is None:
                for line in text:
                    print(line)

                while True:
                    try:
                        dat = input("(Y/N)> ")
                        if dat in ["y", "Y"]:
                            return True
                        elif dat in ["n", "N"]:
                            return False
                    except (KeyboardInterrupt, EOFError):
                        pass

                return False  # Magical fallthrough

            text = [subline for line in text for subline in line.split("\n")]
            maxy, maxx = stdscr.getmaxyx()
            content_height = maxy - 5  # space for borders, label, and prompt
            scroll = 0
            sel = None

            while True:
                stdscr.clear()
                draw_border()
                stdscr.addstr(
                    1,
                    2,
                    label + (" (DRYRUN)" if DRYRUN else ""),
                    curses.A_BOLD | curses.A_UNDERLINE,
                )

                visible_lines = text[scroll : scroll + content_height]
                for i, line in enumerate(visible_lines):
                    stdscr.addstr(3 + i, 2, line[: maxx - 4])

                stdscr.attron(curses.A_REVERSE)
                if sel is True:
                    prompt_line = (
                        " Confirm (Y/N): Y | "
                        + (
                            " SCROLL DOWN --"
                            if scroll + content_height < len(text)
                            else ""
                        )
                        + " Press enter to continue "
                    )
                elif sel is False:
                    prompt_line = (
                        " Confirm (Y/N): N | "
                        + (
                            " SCROLL DOWN --"
                            if scroll + content_height < len(text)
                            else ""
                        )
                        + " Press enter to continue "
                    )
                else:
                    prompt_line = " Confirm (Y/N): "
                stdscr.addstr(maxy - 2, 2, prompt_line)
                stdscr.attroff(curses.A_REVERSE)

                stdscr.refresh()
                try:
                    key = stdscr.getch()
                except KeyboardInterrupt:
                    pass

                if key == ord("\n"):
                    if sel is not None and scroll + content_height >= len(text):
                        break
                elif key in (curses.KEY_DOWN, ord("s"), ord("S")):
                    if scroll + content_height < len(text):
                        scroll += 1
                elif key in (curses.KEY_UP, ord("w"), ord("W")):
                    if scroll > 0:
                        scroll -= 1
                elif key in [ord("y"), ord("Y")]:
                    if sel is not True:
                        sel = True
                elif key in [ord("n"), ord("N")]:
                    if sel is not False:
                        sel = False
                elif sel is not None:
                    sel = None

            wait_clear()
            return sel
        except KeyboardInterrupt:
            pass
        except:
            pass


def selector(
    items: list,
    multi: bool,
    label: str | None = None,
    preselect: int | list = -1,
) -> list | int:
    search_query = ""
    while True:
        try:
            curses.curs_set(0)
            selected = [False] * len(items)
            idx = 0
            offset = 0
            if isinstance(preselect, int):
                if preselect != -1:
                    selected[preselect] = True
                    idx = preselect
            else:
                for i in preselect:
                    selected[i] = True
            start_y = 3
            h, w = stdscr.getmaxyx()
            view_h = h - start_y - 3

            def draw() -> list[tuple[int, str]]:
                stdscr.clear()
                h, w = stdscr.getmaxyx()
                if label:
                    stdscr.addstr(
                        1,
                        2,
                        label + (" (DRYRUN)" if DRYRUN else ""),
                        curses.A_BOLD | curses.A_UNDERLINE,
                    )
                stdscr.addstr(h - 2, 2, "<SPACE>", curses.A_BOLD | curses.A_REVERSE)
                stdscr.addstr(h - 2, 10, "Select", curses.A_BOLD)
                stdscr.addstr(h - 2, 18, "<ENTER>", curses.A_BOLD | curses.A_REVERSE)
                stdscr.addstr(h - 2, 26, "Confirm", curses.A_BOLD)
                stdscr.addstr(h - 2, 35, "<Q>", curses.A_BOLD | curses.A_REVERSE)
                stdscr.addstr(h - 2, 39, "Exit", curses.A_BOLD)
                stdscr.addstr(h - 2, 46, "</>", curses.A_BOLD | curses.A_REVERSE)
                stdscr.addstr(h - 2, 51, "Search", curses.A_BOLD)
                draw_border()

                filtered = [
                    (i, item)
                    for i, item in enumerate(items)
                    if search_query.lower() in item.lower()
                ]

                nonlocal offset, idx
                if idx >= len(filtered):
                    idx = max(0, len(filtered) - 1)
                if idx < offset:
                    offset = idx
                elif idx >= offset + view_h:
                    offset = idx - view_h + 1

                for view_idx in range(view_h):
                    view_idx_global = offset + view_idx
                    if view_idx_global >= len(filtered):
                        break
                    item_idx, item_str = filtered[view_idx_global]
                    y = start_y + view_idx
                    prefix = (
                        "- [x]"
                        if multi and selected[item_idx]
                        else (
                            "- [ ]"
                            if multi
                            else " <*>" if item_idx == filtered[idx][0] else " < >"
                        )
                    )
                    text = f"{prefix} {item_str}"
                    attr = (
                        curses.A_REVERSE
                        if item_idx == filtered[idx][0]
                        else curses.A_NORMAL
                    )
                    stdscr.addnstr(y, 2, text, w - 4, attr)
                stdscr.refresh()
                return filtered

            while True:
                filtered = draw()
                if not filtered:
                    idx = 0
                key = stdscr.getch()

                if key == ord("/"):
                    q = text_input("Search:", prefill=search_query, label=label)
                    if q is None:
                        search_query = ""
                    else:
                        search_query = q
                    idx = 0
                    offset = 0

                elif key == curses.KEY_UP:
                    idx = (idx - 1) % len(filtered) if filtered else 0
                elif key == curses.KEY_DOWN:
                    idx = (idx + 1) % len(filtered) if filtered else 0
                elif key == ord(" ") and multi and filtered:
                    selected[filtered[idx][0]] = not selected[filtered[idx][0]]
                elif key == ord("q"):
                    return [] if multi else None
                elif key in (curses.KEY_ENTER, ord("\n"), ord("\r")):
                    if multi:
                        return [i for i, sel in enumerate(selected) if sel]
                    else:
                        return filtered[idx][0] if filtered else None
                elif key == 27:  # ESC
                    return [] if multi else None
        except KeyboardInterrupt:
            pass
        except:
            pass


def text_input(
    prompt: str = "Input:",
    label: str | None = None,
    prefill: str = "",
    mask: bool = False,
    constraint=None,
) -> str | None:
    if stdscr is None:
        try:
            return input()
        except KeyboardInterrupt:
            return
        except EOFError:
            return
    wait_clear()
    while True:
        try:
            buf = list(prefill)
            cursor = len(buf)
            start_y = 3
            h, w = stdscr.getmaxyx()

            def draw() -> None:
                stdscr.clear()
                if label:
                    stdscr.addstr(
                        1,
                        2,
                        label + (" (DRYRUN)" if DRYRUN else ""),
                        curses.A_BOLD | curses.A_UNDERLINE,
                    )
                stdscr.addstr(h - 2, 2, "<ENTER>", curses.A_BOLD | curses.A_REVERSE)
                stdscr.addstr(h - 2, 10, "Confirm", curses.A_BOLD)
                stdscr.addstr(h - 2, 20, "<ESC>", curses.A_BOLD | curses.A_REVERSE)
                stdscr.addstr(h - 2, 27, "Cancel", curses.A_BOLD)
                draw_border()
                stdscr.addstr(start_y, 2, prompt, curses.A_BOLD)

                display = "*" * len(buf) if mask else "".join(buf)
                line = display.ljust(w - 8)
                stdscr.addstr(start_y + 1, 4, line, curses.A_REVERSE)

                stdscr.move(start_y + 1, 4 + cursor)
                stdscr.refresh()

            while True:
                draw()
                curses.curs_set(1)
                key = stdscr.getch()
                curses.curs_set(0)
                if key in (curses.KEY_ENTER, ord("\n"), ord("\r")):
                    final = "".join(buf)
                    if constraint and not constraint(final):
                        continue
                    return final
                elif key == 27:  # ESC
                    curses.curs_set(0)
                    return
                elif key in (curses.KEY_BACKSPACE, 127, 8):
                    if cursor > 0:
                        cursor -= 1
                        del buf[cursor]
                elif key == curses.KEY_DC:
                    if cursor < len(buf):
                        del buf[cursor]
                elif key == curses.KEY_LEFT:
                    cursor = max(0, cursor - 1)
                elif key == curses.KEY_RIGHT:
                    cursor = min(len(buf), cursor + 1)
                elif 32 <= key <= 126:
                    if len(buf) < w - 9:
                        buf.insert(cursor, chr(key))
                        cursor += 1
        except KeyboardInterrupt:
            pass
        except:
            pass
        curses.curs_set(0)


def draw_border() -> None:
    stdscr.attron(curses.color_pair(1))
    stdscr.border()
    stdscr.attroff(curses.color_pair(1))


def wait_clear(timeout: float = 0.2) -> None:
    stdscr.nodelay(True)
    keys_held = True

    while keys_held:
        try:
            keys_held = False
            start_time = time.time()

            while time.time() - start_time < timeout:
                if stdscr.getch() != -1:
                    keys_held = True
                    break
                time.sleep(0.01)
        except KeyboardInterrupt:
            pass
        except:
            pass

    stdscr.nodelay(False)


def clear_line(y) -> None:
    stdscr.move(y, 0)
    stdscr.clrtoeol()


def draw_list(title: str, options: list, selected: int, special: bool = False) -> None:
    stdscr.addstr(1, 2, title, curses.A_BOLD | curses.A_UNDERLINE)

    h, w = stdscr.getmaxyx()
    for idx, option in enumerate(options):
        x = 4
        y = 3 + idx
        clear_line(y)
        draw_border()
        if idx == selected:
            if special:
                stdscr.addstr(y, x, "[< " + option + " >]")
            else:
                stdscr.attron(curses.A_REVERSE)
                stdscr.addstr(y, x, "[> " + option + " <]")
                stdscr.attroff(curses.A_REVERSE)
        else:
            stdscr.addstr(y, x, option)

    stdscr.refresh()


def draw_menu(title: str, options: list):
    curses.curs_set(0)
    current_row = 0
    wait_clear()
    stdscr.clear()

    while True:
        try:
            draw_list(
                title + (" (DRYRUN)" if DRYRUN else ""),
                options,
                selected=current_row,
            )
            key = stdscr.getch()

            if key == curses.KEY_UP:
                if current_row > 0:
                    current_row -= 1
                else:
                    current_row = len(options) - 1
            elif key == curses.KEY_DOWN:
                if current_row < len(options) - 1:
                    current_row += 1
                else:
                    current_row = 0
            elif key in (curses.KEY_ENTER, ord("\n")):
                draw_list(title, options, selected=current_row)
                time.sleep(0.1)
                draw_list(title, options, selected=current_row, special=True)
                time.sleep(0.1)
                draw_list(title, options, selected=current_row)
                time.sleep(0.1)
                draw_list(title, options, selected=current_row, special=True)
                time.sleep(0.1)
                draw_list(title, options, selected=current_row)
                time.sleep(0.1)
                return current_row
            elif key in (ord("q"), 27):  # ESC or 'q'
                return None
            wait_clear(0.065)
        except KeyboardInterrupt:
            wait_clear()
            stdscr.clear()
        except:
            pass


def suspend() -> None:
    global enabled
    if not enabled:
        return
    enabled = False
    stdscr.clear()
    stdscr.refresh()
    curses.nocbreak()
    stdscr.keypad(False)
    curses.echo()
    curses.endwin()


def resume() -> None:
    global stdscr, enabled
    if enabled:
        return
    stdscr = curses.initscr()
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    enabled = True


def init() -> None:
    global stdscr, enabled
    if enabled:
        return
    resume()
    curses.start_color()
    curses.use_default_colors()
    try:
        curses.init_pair(1, 166, -1)
    except:
        try:
            curses.init_pair(1, curses.COLOR_RED, -1)
        except:
            pass
    stdscr.bkgd(" ", curses.color_pair(1))
    stdscr.clear()
