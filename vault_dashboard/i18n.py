"""UI strings (English and Turkish) and month names."""
from __future__ import annotations

MONTHS = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "tr": ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"],
}

STRINGS = {
    "en": {
        "nav_summary": "Summary", "nav_topics": "Topics", "nav_pipeline": "Pipeline",
        "nav_projects": "Projects", "nav_activity": "Activity",
        "search_ph": "Search the vault…", "lang_other": "TR",
        "stat_topics": "active topics", "stat_week": "jobs in last 7 days",
        "stat_tasks": "open tasks", "stat_published": "published",
        "sec_schedule": "Schedule", "sec_sessions": "Recent sessions", "sec_tasks": "Open tasks",
        "sec_recent": "Recent activity", "full_table": "Full table →", "all_activity": "All activity →",
        "no_tasks": "No open tasks.", "due": "due",
        "topics_ongoing": "Ongoing", "topics_waiting": "Waiting", "topics_closed": "Closed",
        "waiting": "waiting", "next": "Next",
        "th_item": "Item", "th_status": "Status", "published": "published", "in_progress": "in progress",
        "pipeline_legend": "● = the stage's file exists. Stages are read from the files in each folder.",
        "n_notes": "{n} notes", "n_jobs": "{n} events", "last_move": "Last activity",
        "ago_days": "{n} d ago", "ago_hours": "{n} h ago", "just_now": "just now",
        "records": "{n} records", "activity": "Activity", "project_filter": "Project", "all_projects": "All",
        "open_folder": "Folder", "project_activity": "this project's activity",
        "not_found": "Not found", "note_not_found": "Note not found", "folder_not_found": "Folder not found",
        "forbidden": "Refused: path is outside the vault or not a Markdown note.",
        "not_available": "This section is not configured or its source is missing.",
        "search": "Search", "n_results": "{n} results", "error": "Error",
    },
    "tr": {
        "nav_summary": "Özet", "nav_topics": "Konular", "nav_pipeline": "Hat",
        "nav_projects": "Projeler", "nav_activity": "Akış",
        "search_ph": "Kasada ara…", "lang_other": "EN",
        "stat_topics": "aktif konu", "stat_week": "son 7 günde iş",
        "stat_tasks": "açık görev", "stat_published": "yayında",
        "sec_schedule": "Takvim", "sec_sessions": "Son oturumlar", "sec_tasks": "Açık görevler",
        "sec_recent": "Son işler", "full_table": "Tüm tablo →", "all_activity": "Tüm akış →",
        "no_tasks": "Açık görev yok.", "due": "son",
        "topics_ongoing": "Süren", "topics_waiting": "Bekleyen", "topics_closed": "Kapanan",
        "waiting": "bekliyor", "next": "Sıradaki",
        "th_item": "Öğe", "th_status": "Durum", "published": "yayında", "in_progress": "hazırlıkta",
        "pipeline_legend": "● = aşamanın dosyası var. Aşamalar her klasördeki dosyalardan okunur.",
        "n_notes": "{n} not", "n_jobs": "{n} kayıt", "last_move": "Son hareket",
        "ago_days": "{n} gün önce", "ago_hours": "{n} sa önce", "just_now": "az önce",
        "records": "{n} kayıt", "activity": "Akış", "project_filter": "Proje", "all_projects": "Tümü",
        "open_folder": "Klasör", "project_activity": "bu projenin akışı",
        "not_found": "Bulunamadı", "note_not_found": "Not bulunamadı", "folder_not_found": "Klasör bulunamadı",
        "forbidden": "Reddedildi: yol kasanın dışında ya da Markdown notu değil.",
        "not_available": "Bu bölüm yapılandırılmamış ya da kaynağı yok.",
        "search": "Ara", "n_results": "{n} sonuç", "error": "Hata",
    },
}


def tr(lang: str, key: str, **kw) -> str:
    s = STRINGS.get(lang, STRINGS["en"]).get(key) or STRINGS["en"].get(key, key)
    return s.format(**kw) if kw else s
