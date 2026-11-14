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
# تنظيف أجهزة mobile_app القديمة/المكررة (أدمن).
SERVICE_CLEANUP_TRACKERS = "cleanup_stale_trackers"
# طلب موقع لايف لفرد (متاح لأي فرد، مش أدمن بس).
SERVICE_REQUEST_LIVE = "request_live_location"

# app_id اللي تطبيقنا بيسجّل بيه في تكامل mobile_app.
APP_ID = "secure_family"
APP_NAME = "Secure Family"
# أقل عدد أيام بدون تحديث عشان نعتبر جهاز mobile_app قديم.
DEFAULT_STALE_DAYS = 7
# التنظيف التلقائي: كل كام ساعة، وبعد كام يوم بدون تحديث نعتبره ميت.
AUTO_CLEANUP_HOURS = 6
AUTO_STALE_DAYS = 7
# فرق الوقت اللي بعده نعتبر جهازًا مكررًا (نفس الاسم) بقايا ميتة: لازم يكون
# متأخرًا عن الأحدث بأكتر من كده عشان مانمسحش موبايلًا حيًا باسم متشابه.
DUPLICATE_LAG_HOURS = 2

# حدث بيتطلق مع كل تغيير — التطبيقات تقدر تسمعه للتحديث الفوري.
EVENT_UPDATED = "secure_family_config_updated"
# حدث طلب الموقع اللايف — جهاز الفرد المستهدف بيسمعه ويدخل الوضع السريع.
EVENT_LIVE_REQUEST = "familyha_live_request"

# إشارة داخلية لتحديث الكيانات.
SIGNAL_UPDATE = f"{DOMAIN}_update"

# ===== إدارة أجهزة التطبيق: جهاز نشط واحد لكل مستخدم + موافقة الأدمن =====
# تخزين الأجهزة النشطة والطلبات المعلّقة (منفصل عن مخزن الإعداد).
DEVICE_STORAGE_KEY = "secure_family_devices"
DEVICE_STORAGE_VERSION = 1

# خدمات (منطقها في devices.py عشان نفضل ملفات صغيرة منظمة).
SERVICE_CHECK_DEVICE = "check_device"
SERVICE_REQUEST_REGISTRATION = "request_registration"
SERVICE_APPROVE_REGISTRATION = "approve_registration"
SERVICE_DENY_REGISTRATION = "deny_registration"
SERVICE_LIST_PENDING = "list_pending_registrations"

# صلاحية كود الموافقة (دقائق) وأقصى عدد محاولات قبل القفل.
APPROVAL_CODE_TTL_MIN = 10
APPROVAL_MAX_ATTEMPTS = 5

# حدث تنبيه الأدمن بطلب موافقة — بدون كود (الكود سرّي، بييجي عبر خدمة أدمن بس).
EVENT_APPROVAL_REQUEST = "familyha_device_approval"
# حدث خروج فوري: الجهاز القديم بيسمعه ويسجّل خروجه عند الاستبدال.
EVENT_FORCE_LOGOUT = "familyha_force_logout"
# حدث تمت الموافقة: الجهاز الجديد بيسمعه (بمطابقة device_id بتاعه) فيعرف إنه
# اتفعّل — سواء الأدمن وافق من تطبيقه أو بالكود.
EVENT_DEVICE_APPROVED = "familyha_device_approved"
# معرّف الإشعار الثابت لطلب الموافقة (عشان نقدر نلغيه بعد الرد).
NOTIFY_PREFIX = "secure_family_approval_"
