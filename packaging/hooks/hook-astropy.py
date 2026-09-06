"""Keep the runtime data needed by AstroPy without importing optional GUI modules."""

from PyInstaller.utils.hooks import collect_data_files


datas = collect_data_files("astropy")
