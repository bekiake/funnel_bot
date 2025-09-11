import logging
from aiogram.filters import CommandStart, Command
from aiogram import Router, F, types
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from filters.chat_types import ChatTypeFilter
from kbds.inline import (
    get_main_menu_kb, get_back_to_menu_kb, get_premium_menu_kb, 
    get_subscription_plans_kb, get_back_to_premium_menu_kb
)
from kbds.reply import phone_request_kb
from services.funnel import FunnelService
from services.free_link import FreeLinkService
from services.subscription import SubscriptionService
from database.orm_query import (
    orm_add_user, orm_get_active_subscription_plans, orm_get_user, 
    orm_update_user_phone, orm_get_free_link_by_key
)


user_private_router = Router()
user_private_router.message.filter(ChatTypeFilter(["private"]))


class UserStates(StatesGroup):
    waiting_for_phone = State()


@user_private_router.message(CommandStart())
async def start_cmd(message: Message, session: AsyncSession, state: FSMContext):
    """Команда /start"""
    try:
        # Добавляем пользователя в базу данных
        await orm_add_user(
            session=session,
            user_id=message.from_user.id,
            full_name=message.from_user.full_name,
        )
        
        # Проверяем, не админ ли это (админы попадают в admin_private.py)
        logging.info(f"User {message.from_user.id} used /start command")
        
        # Проверяем, есть ли параметр для запуска воронки или freelink
        if message.text and " " in message.text:
            key = message.text.split(" ", 1)[1]
            logging.info(f"User {message.from_user.id} started with key: {key}")
            
            # Avval free link ekanligini tekshiramiz
            free_link_success = await FreeLinkService.process_free_link(message, session, key, state)
            if free_link_success:
                return
            
            # Free link bo'lmasa funnel ni tekshiramiz
            funnel_success = await FunnelService.start_funnel(message, session, key, state)
            if funnel_success:
                return
        
        # Проверяем есть ли у пользователя telefon raqam
        user = await orm_get_user(session, message.from_user.id)
        if not user or not user.phone:
            # Telefon raqam yo'q - so'raymiz
            await message.answer(
                f"👋 <b>Assalomu alaykum, {message.from_user.first_name}!</b>\n\n"
                f"Botdan foydalanish uchun telefon raqamingizni ulashing:",
                reply_markup=phone_request_kb
            )
            await state.set_state(UserStates.waiting_for_phone)
            return
        
        # Telefon raqam bor - asosiy menyuni ko'rsatamiz
        await show_main_menu(message)
        
    except Exception as e:
        logging.error(f"Error in start command: {e}")


@user_private_router.message(UserStates.waiting_for_phone, F.contact)
async def phone_received(message: Message, session: AsyncSession, state: FSMContext):
    """Telefon raqam qabul qilish"""
    try:
        phone = message.contact.phone_number
        
        # Telefon raqamni bazaga saqlash
        await orm_update_user_phone(session, message.from_user.id, phone)
        
        await message.answer(
            "✅ <b>Telefon raqamingiz muvaffaqiyatli saqlandi!</b>",
            reply_markup=types.ReplyKeyboardRemove()
        )
        
        # State datani olish - pending funnel key yoki free link key bormi?
        data = await state.get_data()
        pending_funnel_key = data.get('pending_funnel_key')
        pending_free_link_key = data.get('pending_free_link_key')
        
        await state.clear()
        
        if pending_free_link_key:
            # Pending free link bor - uni davom ettirish
            logging.info(f"Continuing free link '{pending_free_link_key}' for user {message.from_user.id} after phone registration")
            success = await FreeLinkService._grant_free_link_access(
                message, session, 
                await orm_get_free_link_by_key(session, pending_free_link_key)
            )
        elif pending_funnel_key:
            # Pending funnel bor - uni boshlash
            logging.info(f"Continuing funnel '{pending_funnel_key}' for user {message.from_user.id} after phone registration")
            success = await FunnelService._start_funnel_process(message, session, pending_funnel_key)
            if not success:
                # Funnel boshlanmasa asosiy menyuni ko'rsatish
                await show_main_menu(message)
        else:
            # Pending yo'q - asosiy menyuni ko'rsatish
            await show_main_menu(message)
        
    except Exception as e:
        logging.error(f"Error in phone_received: {e}")
        await message.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")


@user_private_router.message(UserStates.waiting_for_phone)
async def phone_invalid(message: Message):
    """Noto'g'ri format telefon raqam"""
    await message.answer(
        "❌ <b>Telefon raqamni to'g'ri formatda yuboring!</b>\n\n"
        "Quyidagi tugma orqali telefon raqamingizni ulashing:",
        reply_markup=phone_request_kb
    )


async def show_main_menu(message: Message):
    """Asosiy menyuni ko'rsatish"""
    await message.answer(
        f"📋 <b>Asosiy menyu</b>\n\n"
        f"Quyidagi menyudan kerakli bo'limni tanlang:",
        reply_markup=get_main_menu_kb()
    )


# ===================== COMMANDS ХЕНДЛЕРЫ =====================

@user_private_router.message(Command("menu"))
async def menu_command(message: Message):
    """Команда /menu"""
    await show_main_menu(message)


@user_private_router.message(Command("premium"))
async def premium_command(message: Message, session: AsyncSession):
    """Команда /premium"""
    try:
        text = (
            "💎 <b>Premium obuna</b>\n\n"
            "Premium obuna bilan quyidagi imkoniyatlarga ega bo'lasiz:\n\n"
            "✅ Barcha premium kurslar\n"
            "✅ Ekskluziv darsliklar\n"
            "✅ Test va amaliy mashqlar\n"
            "✅ Sertifikatlar\n"
            "✅ Shaxsiy nazorat\n\n"
            "Quyidagi bo'limlardan birini tanlang:"
        )
        await message.answer(text, reply_markup=get_premium_menu_kb())
    except Exception as e:
        logging.error(f"Error in premium command: {e}")
        await message.answer("❌ Xatolik yuz berdi")


@user_private_router.message(Command("test"))
async def test_command(message: Message):
    """Команда /test"""
    await message.answer(
        "🧪 <b>Bilim testi</b>\n\n"
        "Test funksiyasi hozirda ishlab chiqilmoqda.\n"
        "Tez orada sizga ma'lum qilamiz!\n\n"
        "📚 Darsliklar bilan tanishib boring: /start",
        reply_markup=get_back_to_menu_kb()
    )


@user_private_router.message(Command("help"))
async def help_command(message: Message):
    """Команда /help"""
    await message.answer(
        "❓ <b>Yordam</b>\n\n"
        "🤖 Bot buyruqlari:\n"
        "/start - Botni ishga tushirish\n"
        "/menu - Asosiy menyu\n"
        "/premium - Premium obuna\n"
        "/test - Bilim testi\n"
        "/help - Yordam\n\n"
        "📞 Qo'llab-quvvatlash: @admin_username\n"
        "📧 Email: support@example.com",
        reply_markup=get_back_to_menu_kb()
    )


# ===================== CALLBACK ХЕНДЛЕРЫ =====================

@user_private_router.callback_query(F.data == "menu_advertising")
async def reklama_handler(callback: CallbackQuery):
    """Обработка кнопки 'Реклама'"""
    text = (
        "📢 <b>Reklama haqida</b>\n\n"
        "Bizning kanalimizda reklama berish uchun quyidagi ma'lumotlarni o'qing:\n\n"
        "💰 Narxlar:\n"
        "• Post uchun: $50\n"
        "• Video uchun: $100\n"
        "• 24 soatlik pin: $200\n\n"
        "📞 Bog'lanish: @admin_username"
    )
    await callback.message.edit_text(text, reply_markup=get_back_to_menu_kb())
    await callback.answer()


@user_private_router.callback_query(F.data == "menu_premium")
async def premium_handler(callback: CallbackQuery, session: AsyncSession):
    """Обработка кнопки 'Premium'"""
    try:
        text = (
            "💎 <b>Premium obuna</b>\n\n"
            "Premium obuna bilan quyidagi imkoniyatlarga ega bo'lasiz:\n\n"
            "✅ Barcha premium kurslar\n"
            "✅ Ekskluziv darsliklar\n"
            "✅ Test va amaliy mashqlar\n"
            "✅ Sertifikatlar\n"
            "✅ Shaxsiy nazorat\n\n"
            "Quyidagi bo'limlardan birini tanlang:"
        )
        await callback.message.edit_text(text, reply_markup=get_premium_menu_kb())
        await callback.answer()
    except Exception as e:
        logging.error(f"Error in premium handler: {e}")
        await callback.answer("❌ Xatolik yuz berdi")


@user_private_router.callback_query(F.data == "premium_plans")
async def premium_plans_handler(callback: CallbackQuery, session: AsyncSession):
    """Обработка кнопки просмотра тарифных планов"""
    print(f"DEBUG: Received callback data: {callback.data}")
    """Premium планлар кўрсатиш"""
    try:
        plans = await orm_get_active_subscription_plans(session)
        
        if not plans:
            text = (
                "🚫 <b>Tarif topilmadi</b>\n\n"
                "Hozirda hech qanday tarif mavjud emas.\n"
                "Keyinroq qaytib ko'ring."
            )
            # Faqat orqaga qaytish tugmasi
            from aiogram.types import InlineKeyboardButton
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            
            builder = InlineKeyboardBuilder()
            builder.add(InlineKeyboardButton(
                text="🔙 Orqaga",
                callback_data="menu_premium"
            ))
            keyboard = builder.as_markup()
        else:
            text = "💎 <b>Premium obuna tariflari:</b>\n\n"
            
            for plan in plans:
                text += f"📋 <b>{plan.name}</b>\n"
                text += f"⏱ Muddati: {plan.duration_days} kun\n"
                text += f"💰 Narxi: ${plan.price_usd} / {plan.price_uzs:,} so'm\n\n"
            
            text += "Tarifni tanlang:"
            keyboard = get_subscription_plans_kb(plans)
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
    except Exception as e:
        logging.error(f"Error showing premium plans: {e}")
        await callback.answer("❌ Xatolik yuz berdi")


@user_private_router.callback_query(F.data == "my_subscriptions")
async def my_subscriptions_handler(callback: CallbackQuery, session: AsyncSession):
    """Фойдаланувчи обуналари"""
    try:
        subscriptions = await SubscriptionService.get_user_subscriptions(session, callback.from_user.id)
        
        if not subscriptions:
            text = "📋 <b>Sizning obunalaringiz</b>\n\n🚫 Hech qanday obuna topilmadi."
        else:
            text = f"📋 <b>Sizning obunalaringiz ({len(subscriptions)}):</b>\n\n"
            
            for sub in subscriptions:
                status = "✅ Faol" if sub.is_active else "❌ Nofaol" 
                text += f"📋 <b>{sub.plan.name}</b>\n"
                text += f"💰 Narx: ${sub.plan.price_usd}\n"
                text += f"⏱ Tugash: {sub.expires_at.strftime('%d.%m.%Y %H:%M')}\n"
                text += f"📊 Status: {status}\n\n"
        
        await callback.message.edit_text(text, reply_markup=get_back_to_premium_menu_kb())
        await callback.answer()
    except Exception as e:
        logging.error(f"Error getting user subscriptions: {e}")
        await callback.answer("❌ Xatolik yuz berdi")


@user_private_router.callback_query(F.data == "about_subscription")
async def about_subscription_handler(callback: CallbackQuery):
    """Обуна ҳақида маълумот"""
    text = (
        "ℹ️ <b>Premium obuna haqida</b>\n\n"
        "🎯 <b>Premium obuna nima beradi:</b>\n\n"
        "✅ Barcha premium kurslariga kirish\n"
        "✅ Ekskluziv video darsliklar\n"
        "✅ Test va amaliy mashqlar\n"
        "✅ Sertifikatlar olish imkoniyati\n"
        "✅ Shaxsiy mentor yordami\n"
        "✅ Premium chat guruhi\n"
        "✅ Haftalik webinarlar\n\n"
        "💡 <b>Qanday to'lash:</b>\n"
        "• Click orqali\n"
        "• Payme orqali\n"
        "• Bank kartasi orqali\n\n"
        "📞 Savollar uchun: @admin_username"
    )
    await callback.message.edit_text(text, reply_markup=get_back_to_premium_menu_kb())
    await callback.answer()


@user_private_router.callback_query(F.data == "menu_info")
async def info_handler(callback: CallbackQuery):
    """Обработка кнопки 'Ma'lumot'"""
    text = (
        "ℹ️ <b>Bot haqida ma'lumot</b>\n\n"
        "🤖 Bu bot orqali siz:\n"
        "• Turli xil darsliklar bilan tanishishingiz\n"
        "• Premium kurslarni sotib olishingiz\n"
        "• Bilimlaringizni test qilishingiz mumkin\n\n"
        "📚 <b>Mavjud yo'nalishlar:</b>\n"
        "• Dasturlash (Python, JavaScript, va boshqalar)\n"
        "• Savdo va marketing\n"
        "• Biznes rivojlantirish\n"
        "• Shaxsiy rivojlanish\n\n"
        "🎯 Bizning maqsadimiz - sizga sifatli ta'lim berish!"
    )
    await callback.message.edit_text(text, reply_markup=get_back_to_menu_kb())
    await callback.answer()


@user_private_router.callback_query(F.data == "menu_help")
async def help_menu_handler(callback: CallbackQuery):
    """Yordam bo'limi"""
    text = (
        "❓ <b>Yordam</b>\n\n"
        "🤖 Bot buyruqlari:\n"
        "/start - Botni ishga tushirish\n"
        "/menu - Asosiy menyu\n"
        "/premium - Premium obuna\n"
        "/test - Bilim testi\n"
        "/help - Yordam\n\n"
        "📞 Qo'llab-quvvatlash: @admin_username\n"
        "📧 Email: support@example.com"
    )
    await callback.message.edit_text(text, reply_markup=get_back_to_menu_kb())
    await callback.answer()


@user_private_router.callback_query(F.data == "back_to_menu")
async def back_to_menu_handler(callback: CallbackQuery):
    """Asosiy menyuga qaytish"""
    await callback.message.edit_text(
        f"📋 <b>Asosiy menyu</b>\n\n"
        f"Quyidagi bo'limlardan birini tanlang:",
        reply_markup=get_main_menu_kb()
    )
    await callback.answer()


# ===================== FUNNEL ХЕНДЛЕРЫ =====================

@user_private_router.callback_query(F.data.startswith("funnel_next:"))
async def funnel_next_step_handler(callback: CallbackQuery, session: AsyncSession):
    """Обработка перехода к следующему шагу воронки"""
    try:
        step_number = int(callback.data.split(":")[1])
        await FunnelService.next_funnel_step(callback, session, step_number)
    except Exception as e:
        logging.error(f"Error in funnel next step: {e}")
        await callback.answer("❌ Xatolik yuz berdi")


# ===================== SUBSCRIPTION ХЕНДЛЕРЫ =====================

@user_private_router.callback_query(F.data.startswith("plan:"))
async def select_plan_handler(callback: CallbackQuery, session: AsyncSession):
    """Обработка выбора плана подписки"""
    try:
        plan_id = int(callback.data.split(":")[1])
        await SubscriptionService.select_plan(callback, session, plan_id)
    except Exception as e:
        logging.error(f"Error selecting plan: {e}")
        await callback.answer("❌ Xatolik yuz berdi")


@user_private_router.callback_query(F.data.startswith("pay:"))
async def payment_handler(callback: CallbackQuery, session: AsyncSession):
    """Обработка платежа"""
    try:
        subscription_id = int(callback.data.split(":")[1])
        await SubscriptionService.process_payment(callback, session, subscription_id)
    except Exception as e:
        logging.error(f"Error processing payment: {e}")
        await callback.answer("❌ Xatolik yuz berdi")


@user_private_router.callback_query(F.data == "cancel_payment")
async def cancel_payment_handler(callback: CallbackQuery):
    """Обработка отмены платежа"""
    await callback.message.edit_text(
        "❌ To'lov bekor qilindi.\n\nAsosiy menyuga qaytish uchun /start ni bosing.",
        reply_markup=get_back_to_menu_kb()
    )
    await callback.answer()


# ===================== УНИВЕРСАЛЬНЫЙ ХЕНДЛЕР =====================

@user_private_router.callback_query()
async def unknown_callback_handler(callback: CallbackQuery):
    """Обработка неизвестных callback запросов"""
    print(f"DEBUG: Unknown callback data: {callback.data}")
    await callback.answer("🤔 Noma'lum buyruq.")

@user_private_router.message()
async def unknown_message_handler(message: Message):
    """Обработка неизвестных сообщений"""
    await message.answer(
        "🤔 Noma'lum buyruq.\n\n"
        "Asosiy menyuga qaytish uchun /start ni bosing:",
        reply_markup=get_main_menu_kb()
    )
