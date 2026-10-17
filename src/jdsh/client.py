import sys
import time
from myjdapi import Myjdapi
from . import config

def query_grabber_packages(device):
    return device.linkgrabber.query_packages([{
        "childCount": True, "bytesTotal": True, "saveTo": True,
        "availableOnlineCount": True, "availableOfflineCount": True,
        "maxResults": -1, "startAt": 0
    }]) or []

def query_grabber_links(device):
    return device.linkgrabber.query_links([{
        "name": True, "url": True, "host": True, "bytesTotal": True,
        "availability": True, "maxResults": -1, "startAt": 0
    }]) or []

def query_download_packages(device):
    return device.downloads.query_packages([{
        "childCount": True, "finished": True, "maxResults": -1, "startAt": 0
    }]) or []

def confirm_links(device, link_ids, package_ids, names, start=False):
    if not start:
        device.linkgrabber.move_to_downloadlist(list(link_ids), list(package_ids))
        return []

    known = {p['uuid'] for p in query_download_packages(device)}
    device.linkgrabber.move_to_downloadlist(list(link_ids), list(package_ids))

    # Moved packages get new IDs (or merge into a same-named one), so match by name
    names = set(names)
    moved = {}
    for _ in range(20):
        moved = {p['uuid']: p['name'] for p in query_download_packages(device)
                 if p['name'] in names and (p['uuid'] not in known or not p.get('finished'))}
        if set(moved.values()) >= names:
            break
        time.sleep(0.25)
    if moved:
        device.downloads.force_download([], list(moved))
    return list(moved.values())

class JDClient:
    def __init__(self):
        self.api = Myjdapi()
        self.api.set_app_key(config.APP_KEY)
        self.device = None

    def connect(self):
        try:
            if not self.api.direct_connect(config.HOST, config.PORT):
                raise ConnectionError(f"Failed to connect to {config.HOST}:{config.PORT}")
            self.device = self.api.get_device()
            return self.device
        except Exception as e:
            print(f"Connection Error: {e}", file=sys.stderr)
            sys.exit(1)

    def fetch_stats(self):
        try:
            state = self.device.downloadcontroller.get_current_state()
            
            links = self.device.downloads.query_links([{
                "name": True, "bytesLoaded": True, "bytesTotal": True, 
                "speed": True, "running": True, "eta": True, "status": True,
                "finished": True, "enabled": True, "uuid": True
            }])
            
            active = []
            pending = []
            
            for l in links:
                if l.get('finished'):
                    continue
                
                # Active
                if l.get('running'):
                    active.append(l)
                # Pending
                elif l.get('enabled'):
                    pending.append(l)
                    
            return state, active, pending
        except Exception:
            return "ERROR", [], []

    def toggle_state(self, current_state):
        if current_state in ["RUNNING", "DOWNLOADING"]:
            self.device.downloadcontroller.stop_downloads()
        else:
            self.device.downloadcontroller.start_downloads()

    def fetch_grabber(self):
        try:
            return query_grabber_packages(self.device), query_grabber_links(self.device)
        except Exception:
            return None

    def confirm(self, link_ids, package_ids, names, start=False):
        return confirm_links(self.device, link_ids, package_ids, names, start)

    def remove_from_grabber(self, link_ids, package_ids):
        self.device.linkgrabber.remove_links(list(link_ids), list(package_ids))
