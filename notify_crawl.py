#!/usr/bin/env python3
"""
Monitor crawl job and send Windows notification when complete.
"""

import time
import subprocess
import requests

JOB_ID = "crawl_245298e9e46c48d9"
API_BASE = "http://localhost:8000"

def send_windows_notification(title: str, message: str):
    """Send a Windows toast notification via PowerShell."""
    ps_script = f'''
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
    $template = @"
    <toast>
        <visual>
            <binding template="ToastText02">
                <text id="1">{title}</text>
                <text id="2">{message}</text>
            </binding>
        </visual>
        <audio src="ms-winsoundevent:Notification.Default"/>
    </toast>
"@
    $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
    $xml.LoadXml($template)
    $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("SimpleCrawl").Show($toast)
    '''
    subprocess.run(["powershell.exe", "-Command", ps_script], capture_output=True)

def check_status():
    """Check crawl job status."""
    try:
        resp = requests.get(f"{API_BASE}/v1/crawl/{JOB_ID}", timeout=10)
        return resp.json()
    except:
        return None

def main():
    print(f"Monitoring crawl job: {JOB_ID}")
    print("Will notify when complete. Press Ctrl+C to stop monitoring.\n")

    while True:
        status = check_status()
        if not status:
            print("  API not responding, retrying...")
            time.sleep(30)
            continue

        job_status = status.get("status", "unknown")
        completed = status.get("completed", 0)
        total = status.get("total", 0)
        failed = status.get("failed", 0)

        print(f"  Status: {job_status} | Pages: {completed}/{total} | Failed: {failed}")

        if job_status == "completed":
            msg = f"Crawled {completed} pages successfully!"
            print(f"\n*** CRAWL COMPLETE: {msg} ***\n")
            send_windows_notification("Ashes Wiki Crawl Complete", msg)
            break
        elif job_status == "failed":
            error = status.get("error", "Unknown error")
            print(f"\n*** CRAWL FAILED: {error} ***\n")
            send_windows_notification("Ashes Wiki Crawl Failed", error[:100])
            break

        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    main()
