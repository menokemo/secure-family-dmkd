"""Constants for the Secure Family integration."""

DOMAIN = "secure_family"

# تخزين دائم في .storage — بيعيش بعد أي restart.
STORAGE_KEY = "secure_family_config"
STORAGE_VERSION = 1

# أقصى عدد نسخ سابقة نحتفظ بيها للـrollback.
MAX_HISTORY = 10

# الخدمات (الأدمن بس هو اللي ينفّذها).
SERVICE_SET_CONFIG = "set_config"
SERVICE_ROLLBACK = "rollback"
SERVICE_CLEAR = "clear_config"

# حدث بيتطلق مع كل تغيير — التطبيقات تقدر تسمعه للتحديث الفوري.
EVENT_UPDATED = "secure_family_config_updated"

# إشارة داخلية لتحديث الكيانات.
SIGNAL_UPDATE = f"{DOMAIN}_update"
