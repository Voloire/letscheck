"""Minimal command-aware client for the SkyChart V4 TCP protocol."""

from __future__ import annotations

import re
import socket
import math
import uuid


TERMINALS = ("OK!", "Failed!", "Not found!", "Timeout!", "Bye!")


class SkyChartError(Exception):
    """Base error safe for translation at the HTTP boundary."""


class SkyChartConnectionError(SkyChartError):
    pass


class SkyChartProtocolError(SkyChartError):
    pass


class SkyChartObjectError(SkyChartError):
    pass


def parse_selected_object(response):
    if not isinstance(response, str) or not response.startswith("OK! "):
        raise SkyChartObjectError("SkyChart did not resolve the requested object")
    fields = response[4:].split("\t")
    if len(fields) < 4:
        raise SkyChartProtocolError("Descrizione dell'oggetto SkyChart incompleta")
    frame = next((field.strip() for field in fields[4:] if field.strip().casefold().startswith("equinox:")), None)
    if frame is None or frame.casefold() != "equinox:now":
        raise SkyChartProtocolError("SkyChart returned coordinates with an unsupported equinox")

    ra_text = fields[0].strip()
    dec_text = fields[1].strip()
    try:
        ra_hours = float(ra_text)
    except ValueError:
        match = re.fullmatch(r"(\d{1,2})h(\d{1,2})m(\d+(?:\.\d+)?)s", ra_text)
        if not match:
            raise SkyChartProtocolError("SkyChart right ascension was not recognized")
        hours, minutes, seconds = (float(value) for value in match.groups())
        ra_hours = hours + minutes / 60.0 + seconds / 3600.0
    try:
        declination = float(dec_text)
    except ValueError:
        numbers = re.findall(r"[+-]?\d+(?:\.\d+)?", dec_text)
        if len(numbers) != 3:
            raise SkyChartProtocolError("SkyChart declination was not recognized")
        degrees, minutes, seconds = (float(value) for value in numbers)
        sign = -1.0 if dec_text.lstrip().startswith("-") else 1.0
        declination = sign * (abs(degrees) + minutes / 60.0 + seconds / 3600.0)
    if not math.isfinite(ra_hours) or not math.isfinite(declination):
        raise SkyChartProtocolError("SkyChart coordinates are not finite")
    if not 0 <= ra_hours <= 24 or not -90 <= declination <= 90:
        raise SkyChartProtocolError("Coordinate SkyChart fuori intervallo")
    return {
        "ra": (ra_hours * 15.0) % 360.0,
        "dec": declination,
        "kind": fields[2].strip(),
        "name": fields[3].strip(),
    }


class SkyChartClient:
    def __init__(self, host="127.0.0.1", port=3292, timeout=5.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.socket = None
        self.reader = None
        self.initial_chart = None
        self.temporary_chart = None
        try:
            self.socket = socket.create_connection((host, port), timeout)
            self.socket.settimeout(timeout)
            self.reader = self.socket.makefile("rb")
            banner = self._read_substantive_line()
        except (OSError, TimeoutError) as exc:
            self.close()
            raise SkyChartConnectionError("Impossibile collegarsi al server SkyChart") from exc
        match = re.fullmatch(r"OK! id=\d+ chart=(.*)", banner)
        if not match:
            self.close()
            raise SkyChartProtocolError("Initial SkyChart response was not recognized")
        self.initial_chart = match.group(1)

    @staticmethod
    def quote(value):
        if not isinstance(value, str) or not value.strip():
            raise SkyChartProtocolError("Object name is invalid")
        if any(character in value for character in ('"', "\r", "\n", "\x00")):
            raise SkyChartProtocolError("Object name contains unsupported characters")
        return f'"{value.strip()}"'

    def _read_substantive_line(self):
        while True:
            try:
                raw = self.reader.readline(4097)
            except (OSError, TimeoutError) as exc:
                raise SkyChartConnectionError("SkyChart did not respond before the timeout") from exc
            if not raw:
                raise SkyChartConnectionError("SkyChart ha chiuso la connessione")
            if len(raw) > 4096:
                raise SkyChartProtocolError("Risposta SkyChart troppo lunga")
            try:
                line = raw.decode("utf-8")
            except UnicodeDecodeError:
                line = raw.decode("cp1252", errors="replace")
            line = line.rstrip("\r\n")
            if not line or line == "." or line.startswith(">\t"):
                continue
            return line

    def _send(self, command):
        if not isinstance(command, str) or not command or any(c in command for c in "\r\n\x00"):
            raise SkyChartProtocolError("SkyChart command is invalid")
        if len(command.encode("utf-8")) > 1022:
            raise SkyChartProtocolError("Comando SkyChart troppo lungo")
        try:
            self.socket.sendall(command.encode("utf-8") + b"\r\n")
        except OSError as exc:
            raise SkyChartConnectionError("Connessione a SkyChart interrotta") from exc

    def command(self, command):
        self._send(command)
        lines = []
        while True:
            line = self._read_substantive_line()
            lines.append(line)
            if line.startswith(TERMINALS):
                return "\n".join(lines)

    def require_ok(self, command):
        response = self.command(command)
        final_line = response.rsplit("\n", 1)[-1]
        if not final_line.startswith("OK!"):
            raise SkyChartProtocolError("SkyChart ha rifiutato un comando necessario")
        return response

    def chart_equinox(self):
        self._send("GETCHARTEQSYS")
        response = self._read_substantive_line()
        if response.startswith(("Failed!", "Timeout!")):
            raise SkyChartProtocolError("SkyChart did not provide a coordinate system")
        return response

    def status(self):
        return self.command("LISTCHART").startswith("OK!")

    @staticmethod
    def _dms(value, width):
        sign = "+" if value >= 0 else "-"
        absolute = abs(float(value))
        degrees = int(absolute)
        minutes_float = (absolute - degrees) * 60.0
        minutes = int(minutes_float)
        seconds = (minutes_float - minutes) * 60.0
        return f"{sign}{degrees:0{width}d}d{minutes:02d}m{seconds:05.2f}s"

    def start_temporary(self, latitude, longitude):
        name = f"AstroChecker_{uuid.uuid4().hex[:12]}"
        self.require_ok(f"NEWCHART {name}")
        self.temporary_chart = name
        self.require_ok(f"SELECTCHART {name}")
        self.require_ok("SETTZ Etc/GMT")
        latitude_text = self._dms(latitude, 2)
        longitude_text = self._dms(-longitude, 3)
        self.require_ok(
            f"SETOBS LAT:{latitude_text}LON:{longitude_text} ALT:000mOBS:AstroChecker"
        )
        self.require_ok("SETPROJ ALTAZ")
        equinox = self.chart_equinox()
        if equinox.casefold() != "date":
            raise SkyChartProtocolError(
                "SkyChart deve restituire coordinate con equinozio 'Date'; disattivare l'override J2000 del server"
            )

    def set_date(self, instant):
        utc = instant.astimezone(__import__("datetime").timezone.utc)
        self.require_ok(f"SETDATE {utc:%Y-%m-%dT%H:%M:%S}")

    def lookup(self, name, object_class=None):
        quoted = self.quote(name)
        command = f"FIND {int(object_class)} {quoted}" if object_class is not None else f"SEARCH {quoted}"
        response = self.command(command)
        if not response.rsplit("\n", 1)[-1].startswith("OK!"):
            raise SkyChartObjectError(f"SkyChart could not find object '{name}'")
        return parse_selected_object(self.command("GETSELECTEDOBJECT"))

    def finish_temporary(self):
        temporary, self.temporary_chart = self.temporary_chart, None
        if temporary is None:
            return
        error = None
        if self.initial_chart and all(c not in self.initial_chart for c in ('"', "\r", "\n", "\x00")):
            try:
                self.require_ok(f"SELECTCHART {self.initial_chart}")
            except SkyChartError as exc:
                error = exc
        try:
            self.require_ok(f"CLOSECHART {temporary}")
        except SkyChartError as exc:
            error = error or exc
        if error is not None:
            raise error

    def close(self):
        reader, self.reader = self.reader, None
        sock, self.socket = self.socket, None
        if reader is not None:
            try:
                reader.close()
            except OSError:
                pass
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()
