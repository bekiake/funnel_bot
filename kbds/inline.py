from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.models import SubscriptionPlan


# ===================== ОСНОВНЫЕ МЕНЮ =====================

def get_main_menu_kb():
    """Главное меню пользователя"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="📢 Reklama haqida",
        callback_data="menu_advertising"
    ))
    
    builder.add(InlineKeyboardButton(
        text="💎 Premium obuna",
        callback_data="menu_premium"
    ))
    
    builder.add(InlineKeyboardButton(
        text="ℹ️ Ma'lumot",
        callback_data="menu_info"
    ))
    
    builder.add(InlineKeyboardButton(
        text="❓ Yordam",
        callback_data="menu_help"
    ))
    
    builder.adjust(1)  # По одной кнопке в ряд
    return builder.as_markup()


def get_admin_menu_kb():
    """Админское меню"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="📊 Statistika",
        callback_data="admin_stats"
    ))
    
    builder.add(InlineKeyboardButton(
        text="👥 Foydalanuvchilar",
        callback_data="admin_users"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🔊 Broadcast",
        callback_data="admin_broadcast"
    ))
    
    builder.add(InlineKeyboardButton(
        text="➕ Funnel yaratish",
        callback_data="admin_create_funnel"
    ))
    
    builder.add(InlineKeyboardButton(
        text="📂 Funnel ro'yxati",
        callback_data="admin_funnel_list"
    ))
    
    builder.add(InlineKeyboardButton(
        text="💰 Tariflar",
        callback_data="admin_tariffs"
    ))
    
    builder.add(InlineKeyboardButton(
        text="📋 Obunalar",
        callback_data="admin_subscriptions"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🎁 Free linklar",
        callback_data="admin_free_links"
    ))
    
    builder.adjust(2)  # По две кнопки в ряд
    return builder.as_markup()


def get_broadcast_kb():
    """Broadcast uchun keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="❌ Bekor qilish",
        callback_data="cancel_broadcast"
    ))
    
    builder.adjust(1)
    return builder.as_markup()


def get_funnel_creation_kb():
    """Клавиатура для создания воронки"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="📝 Matn qo'shish",
        callback_data="funnel_add_text"
    ))
    
    builder.add(InlineKeyboardButton(
        text="📷 Rasm qo'shish",
        callback_data="funnel_add_photo"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🎥 Video qo'shish",
        callback_data="funnel_add_video"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🎵 Audio qo'shish",
        callback_data="funnel_add_audio"
    ))
    
    builder.add(InlineKeyboardButton(
        text="📎 Fayl qo'shish",
        callback_data="funnel_add_document"
    ))
    
    builder.add(InlineKeyboardButton(
        text="✅ Tugallash",
        callback_data="funnel_finish"
    ))
    
    builder.add(InlineKeyboardButton(
        text="❌ Bekor qilish",
        callback_data="funnel_cancel"
    ))
    
    builder.adjust(2)  # По две кнопки в ряд
    return builder.as_markup()


def get_funnel_cancel_kb():
    """Bekor qilish klaviaturasi funnel yaratish uchun"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="❌ Bekor qilish",
        callback_data="funnel_cancel"
    ))
    
    return builder.as_markup()


def get_funnel_content_kb():
    """Kontent yuborganda bekor qilish klaviaturasi"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="🔙 Orqaga",
        callback_data="funnel_back_to_steps"
    ))
    
    builder.add(InlineKeyboardButton(
        text="❌ Bekor qilish",
        callback_data="funnel_cancel"
    ))
    
    builder.adjust(1)
    return builder.as_markup()


# ===================== ВОРОНКИ =====================

def get_funnel_next_step_kb(step_number: int, total_steps: int, button_text: str = "Keyingi ➡️"):
    """Клавиатура для перехода к следующему шагу воронки"""
    builder = InlineKeyboardBuilder()
    
    if step_number < total_steps:
        builder.add(InlineKeyboardButton(
            text=button_text,
            callback_data=f"funnel_next:{step_number + 1}"
        ))
    
    return builder.as_markup()


# ===================== ПОДПИСКИ =====================


def get_subscription_plans_kb(plans: list[SubscriptionPlan]):
    """Клавиатура с планами подписки"""
    builder = InlineKeyboardBuilder()
    
    for plan in plans:
        builder.add(InlineKeyboardButton(
            text=f"{plan.name} - ${plan.price_usd}",
            callback_data=f"plan:{plan.id}"
        ))
    
    # Кнопка возврата
    builder.add(InlineKeyboardButton(
        text="🔙 Premium menyuga",
        callback_data="menu_premium"
    ))
    
    builder.adjust(1)  # По одной кнопке в ряд
    return builder.as_markup()


def get_payment_kb(subscription_id: int, price_usd: float, price_uzs: int):
    """Клавиатура для оплаты подписки"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text=f"💳 To'lash ${price_usd} / {price_uzs:,} so'm",
        callback_data=f"pay:{subscription_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="❌ Bekor qilish",
        callback_data="cancel_payment"
    ))
    
    # Кнопка возврата к планам
    builder.add(InlineKeyboardButton(
        text="🔙 Tariflarga qaytish",
        callback_data="menu_premium"
    ))
    
    builder.adjust(1)
    return builder.as_markup()


def get_payment_verification_kb(subscription_id: int):
    """Клавиатура для подтверждения оплаты"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="✅ To'lovni tasdiqlash",
        callback_data=f"verify_payment:{subscription_id}"
    ))
    
    # Кнопка возврата к планам
    builder.add(InlineKeyboardButton(
        text="🔙 Tariflarga qaytish",
        callback_data="menu_premium"
    ))
    
    builder.adjust(1)
    return builder.as_markup()


def get_admin_subscription_kb():
    """Админская клавиатура для управления подписками"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="📋 Tariflar ro'yxati",
        callback_data="admin_plans_list"
    ))
    
    builder.add(InlineKeyboardButton(
        text="➕ Yangi tarif qo'shish",
        callback_data="admin_add_plan"
    ))
    
    builder.add(InlineKeyboardButton(
        text="📊 Statistika",
        callback_data="admin_subscription_stats"
    ))
    
    # Кнопка возврата в админ меню
    builder.add(InlineKeyboardButton(
        text="🔙 Admin menyuga qaytish",
        callback_data="back_to_admin_menu"
    ))
    
    builder.adjust(1)
    return builder.as_markup()


# ===================== ДОПОЛНИТЕЛЬНЫЕ КЛАВИАТУРЫ С КНОПКАМИ ВОЗВРАТА =====================

def get_back_to_admin_menu_kb():
    """Клавиатура для возврата в админское меню"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="🔙 Admin menyuga qaytish",
        callback_data="back_to_admin_menu"
    ))
    
    return builder.as_markup()


def get_cancel_add_plan_kb():
    """Клавиатура для отмены добавления тарифа"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="❌ Bekor qilish",
        callback_data="cancel_subscription_creation"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🔙 Admin menyuga qaytish",
        callback_data="back_to_admin_menu"
    ))
    
    return builder.as_markup()


def get_back_to_menu_kb():
    """Клавиатура для возврата в главное меню"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="🔙 Bosh menuga qaytish",
        callback_data="back_to_menu"
    ))
    
    return builder.as_markup()


def get_back_to_premium_menu_kb():
    """Клавиатура для возврата в премиум меню"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="🔙 Premium menyuga",
        callback_data="menu_premium"
    ))
    
    return builder.as_markup()


def get_subscription_plans_back_kb():
    """Клавиатура с планами подписки и кнопкой возврата"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="🔙 Bosh menuga qaytish", 
        callback_data="back_to_menu"
    ))
    
    return builder.as_markup()


def get_users_list_kb(users, page=0, per_page=10):
    """Foydalanuvchilar ro'yxati uchun keyboard"""
    builder = InlineKeyboardBuilder()
    
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_users = users[start_idx:end_idx]
    
    # Har bir foydalanuvchi uchun tugma
    for user in page_users:
        # user obyektidan ID va ismni ajratamiz
        if hasattr(user, 'id') and hasattr(user, 'full_name'):
            user_id = user.id
            user_name = user.full_name
        else:
            # Agar string bo'lsa, parse qilamiz
            parts = str(user).split(' - ')
            if len(parts) >= 2:
                user_id = parts[0]
                user_name = ' - '.join(parts[1:])
            else:
                user_id = str(user)
                user_name = str(user)
        
        builder.add(InlineKeyboardButton(
            text=f"👤 {user_name}",
            callback_data=f"user_profile:{user_id}"
        ))
    
    # Pagination tugmalari
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(
            text="⬅️ Oldingi",
            callback_data=f"users_page:{page-1}"
        ))
    
    if end_idx < len(users):
        nav_buttons.append(InlineKeyboardButton(
            text="Keyingi ➡️",
            callback_data=f"users_page:{page+1}"
        ))
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    # Orqaga tugmasi
    builder.add(InlineKeyboardButton(
        text="🔙 Admin paneliga",
        callback_data="back_to_admin_menu"
    ))
    
    builder.adjust(1)  # Har qatorda bitta tugma
    return builder.as_markup()


def get_user_profile_kb(user_id):
    """Foydalanuvchi profili uchun keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="📊 Statistika",
        callback_data=f"user_stats:{user_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="📝 Xabar yuborish",
        callback_data=f"send_message:{user_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🚫 Bloklash",
        callback_data=f"block_user:{user_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🔙 Foydalanuvchilarga",
        callback_data="admin_users"
    ))
    
    builder.adjust(1)
    return builder.as_markup()


def get_funnels_list_kb(funnels):
    """Funnel ro'yxati uchun keyboard"""
    builder = InlineKeyboardBuilder()
    
    for funnel in funnels:
        builder.add(InlineKeyboardButton(
            text=f"🎯 {funnel.name}",
            callback_data=f"funnel_details:{funnel.id}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="➕ Yangi funnel yaratish",
        callback_data="admin_create_funnel"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🔙 Admin paneliga",
        callback_data="back_to_admin_menu"
    ))
    
    builder.adjust(1)
    return builder.as_markup()


def get_funnel_details_kb(funnel_id):
    """Funnel tafsilotlari uchun keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="📊 Statistika",
        callback_data=f"funnel_stats:{funnel_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="✏️ Tahrirlash",
        callback_data=f"funnel_edit:{funnel_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🗑 O'chirish",
        callback_data=f"funnel_delete:{funnel_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🔙 Funnel ro'yxati",
        callback_data="admin_funnel_list"
    ))
    
    builder.adjust(1)
    return builder.as_markup()


def get_subscriptions_list_kb(plans):
    """Obunalar ro'yxati uchun keyboard"""
    builder = InlineKeyboardBuilder()
    
    for plan in plans:
        builder.add(InlineKeyboardButton(
            text=f"💎 {plan.name} - ${plan.price_usd}",
            callback_data=f"subscription_details:{plan.id}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="➕ Yangi tarif yaratish",
        callback_data="admin_add_plan"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🔙 Orqaga",
        callback_data="admin_tariffs"
    ))
    
    builder.adjust(1)
    return builder.as_markup()


def get_subscription_details_kb(plan_id):
    """Obuna tafsilotlari uchun keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="📊 Statistika",
        callback_data=f"subscription_stats:{plan_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="✏️ Tahrirlash",
        callback_data=f"subscription_edit:{plan_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🗑 O'chirish",
        callback_data=f"subscription_delete:{plan_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🔙 Obunalar ro'yxati",
        callback_data="admin_subscriptions"
    ))
    
    builder.adjust(1)
    return builder.as_markup()


def get_premium_menu_kb():
    """Premium obuna menyusi"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="💎 Obuna tariflari",
        callback_data="premium_plans"
    ))
    
    builder.add(InlineKeyboardButton(
        text="📊 Mening obunalarim",
        callback_data="my_subscriptions"
    ))
    
    builder.add(InlineKeyboardButton(
        text="❓ Obuna haqida",
        callback_data="about_subscription"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🔙 Asosiy menyuga",
        callback_data="back_to_menu"
    ))
    
    builder.adjust(1)
    return builder.as_markup()


# ===================== FREE LINK KEYBOARDS =====================

def get_free_links_menu_kb():
    """Free linklar menyusi"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="➕ Yangi free link",
        callback_data="create_free_link"
    ))
    
    builder.add(InlineKeyboardButton(
        text="📋 Free linklar ro'yxati",
        callback_data="free_links_list"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🔙 Orqaga",
        callback_data="back_to_admin_menu"
    ))
    
    builder.adjust(1)
    return builder.as_markup()


def get_free_links_list_kb(free_links):
    """Free linklar ro'yxati klaviaturasi"""
    builder = InlineKeyboardBuilder()
    
    for link in free_links:
        status = "🟢" if link.is_active else "🔴"
        builder.add(InlineKeyboardButton(
            text=f"{status} {link.name} ({link.current_uses}/{link.max_uses})",
            callback_data=f"free_link_info_{link.id}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="🔙 Orqaga",
        callback_data="admin_free_links"
    ))
    
    builder.adjust(1)
    return builder.as_markup()


def get_free_link_info_kb(free_link_id, is_active=True):
    """Free link ma'lumotlari klaviaturasi"""
    builder = InlineKeyboardBuilder()
    
    # Status boshqarish tugmasi
    if is_active:
        builder.add(InlineKeyboardButton(
            text="🔴 Faolsizlashtirish",
            callback_data=f"toggle_free_link_{free_link_id}"
        ))
    else:
        builder.add(InlineKeyboardButton(
            text="🟢 Faollashtirish",
            callback_data=f"toggle_free_link_{free_link_id}"
        ))
    
    # Yumshoq o'chirish (faolsizlashtirish)
    builder.add(InlineKeyboardButton(
        text="🚫 Deaktivatsiya",
        callback_data=f"deactivate_free_link_{free_link_id}"
    ))
    
    # Qattiq o'chirish (butunlay olib tashlash)
    builder.add(InlineKeyboardButton(
        text="🗑️ Butunlay o'chirish",
        callback_data=f"permanent_delete_free_link_{free_link_id}"
    ))
    
    builder.add(InlineKeyboardButton(
        text="🔙 Orqaga",
        callback_data="free_links_list"
    ))
    
    builder.adjust(1, 2, 1)
    return builder.as_markup()


def get_free_link_cancel_kb():
    """Free link yaratishni bekor qilish"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="❌ Bekor qilish",
        callback_data="admin_free_links"
    ))
    
    return builder.as_markup()


def get_freelink_access_kb(channel_invite_link):
    """Freelink orqali kirgan foydalanuvchi uchun kanal tugmasi"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="📢 Kanalga qo'shilish",
        url=channel_invite_link
    ))
    
    builder.adjust(1)
    return builder.as_markup()


def get_max_users_selection_kb():
    """Maksimal foydalanuvchilar sonini tanlash klaviaturasi"""
    builder = InlineKeyboardBuilder()
    
    # Birinchi qator - kichik raqamlar
    builder.add(InlineKeyboardButton(text="1", callback_data="max_users_1"))
    builder.add(InlineKeyboardButton(text="5", callback_data="max_users_5"))
    builder.add(InlineKeyboardButton(text="10", callback_data="max_users_10"))
    
    # Ikkinchi qator - o'rta raqamlar
    builder.add(InlineKeyboardButton(text="25", callback_data="max_users_25"))
    builder.add(InlineKeyboardButton(text="50", callback_data="max_users_50"))
    builder.add(InlineKeyboardButton(text="100", callback_data="max_users_100"))
    
    # Uchinchi qator - katta raqamlar va cheksiz
    builder.add(InlineKeyboardButton(text="500", callback_data="max_users_500"))
    builder.add(InlineKeyboardButton(text="♾️ Cheksiz", callback_data="max_users_unlimited"))
    
    # Bekor qilish tugmasi
    builder.add(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_free_links"))
    
    builder.adjust(3, 3, 2, 1)
    return builder.as_markup()


def get_duration_selection_kb():
    """Muddat tanlash klaviaturasi"""
    builder = InlineKeyboardBuilder()
    
    # Birinchi qator - kunlar
    builder.add(InlineKeyboardButton(text="1 kun", callback_data="duration_1_day"))
    builder.add(InlineKeyboardButton(text="3 kun", callback_data="duration_3_days"))
    builder.add(InlineKeyboardButton(text="7 kun", callback_data="duration_7_days"))
    
    # Ikkinchi qator - haftalar
    builder.add(InlineKeyboardButton(text="2 hafta", callback_data="duration_14_days"))
    builder.add(InlineKeyboardButton(text="1 oy", callback_data="duration_30_days"))
    builder.add(InlineKeyboardButton(text="3 oy", callback_data="duration_90_days"))
    
    # Uchinchi qator - uzoq muddat
    builder.add(InlineKeyboardButton(text="6 oy", callback_data="duration_180_days"))
    builder.add(InlineKeyboardButton(text="1 yil", callback_data="duration_365_days"))
    builder.add(InlineKeyboardButton(text="♾️ Cheksiz", callback_data="duration_unlimited"))
    
    # Bekor qilish tugmasi
    builder.add(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_free_links"))
    
    builder.adjust(3, 3, 3, 1)
    return builder.as_markup()


def get_delete_confirmation_kb(free_link_id, delete_type="permanent"):
    """Free link o'chirishni tasdiqlash klaviaturasi"""
    builder = InlineKeyboardBuilder()
    
    if delete_type == "permanent":
        builder.add(InlineKeyboardButton(
            text="✅ Ha, butunlay o'chirish",
            callback_data=f"confirm_permanent_delete_{free_link_id}"
        ))
        builder.add(InlineKeyboardButton(
            text="❌ Yo'q, bekor qilish",
            callback_data=f"free_link_info_{free_link_id}"
        ))
    else:  # deactivate
        builder.add(InlineKeyboardButton(
            text="✅ Ha, deaktivatsiya qilish",
            callback_data=f"confirm_deactivate_{free_link_id}"
        ))
        builder.add(InlineKeyboardButton(
            text="❌ Yo'q, bekor qilish",
            callback_data=f"free_link_info_{free_link_id}"
        ))
    
    builder.adjust(1, 1)
    return builder.as_markup()
