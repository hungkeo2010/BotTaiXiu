import logging
import random
import asyncio
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- DỮ LIỆU HỆ THỐNG ---
users_db = {}       # Lưu thông tin người chơi
giftcode_db = {}    # Kho lưu trữ giftcode
pending_nap = {}    # Lưu trữ mã nạp chờ duyệt

# ID Admin chính thức
ADMIN_IDS = [8682451039]

# --- QUAN TRỌNG: ĐIỀN CHAT ID CỦA NHÓM VÀO ĐÂY (VD: -1001234567890) ---
GROUP_CHAT_ID = None  

# Biến toàn cục quản lý phiên Tài Xỉu
forced_dice_result = None
current_session = 199560
huvang_pool = 284440
session_bets = {"T": 0, "X": 0, "C": 0, "L": 0}
user_session_bets = {}  
history_sessions = [
    ("🔴", "⚫"), ("🔵", "🔵"), ("🔵", "🔵"), ("🔵", "⚫"),
    ("🔴", "⚫"), ("🔵", "🔵"), ("🔴", "⚫"), ("🔵", "⚫"),
    ("🔴", "⚫"), ("🔴", "⚫"), ("🔴", "⚪"), ("🔴", "⚫")
] 

def get_user(user_id):
    if user_id not in users_db:
        users_db[user_id] = {
            "balance": 0,
            "total_bet": 0,
            "vip_points": 0,
            "vip_level": "Đồng 🥉",
            "is_newbie": True,  
            "bank_info": None,  
            "history_nap": [],
            "history_rut": [],
            "history_choi": []
        }
    return users_db[user_id]

def update_vip(user_data):
    total = user_data["total_bet"]
    points = total // 100000  
    user_data["vip_points"] = points
    
    if points >= 1000:
        user_data["vip_level"] = "Chiến Tướng 👑"
    elif points >= 500:
        user_data["vip_level"] = "Cao Thủ 🔥"
    elif points >= 200:
        user_data["vip_level"] = "Kim Cương 💎"
    elif points >= 100:
        user_data["vip_level"] = "Vàng ⭐"
    elif points >= 50:
        user_data["vip_level"] = "Bạc 🥈"
    else:
        user_data["vip_level"] = "Đồng 🥉"

def get_main_menu():
    keyboard = [
        ["📁 Danh sách game", "📄 Tài khoản"],
        ["💲 Nạp Tiền", "💳 Rút Tiền"],
        ["🌸 Chuyển Tiền", "🚀 Dua top"],
        ["🎁 Event", "🔍 Lệnh"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    get_user(user_id)
    text = (
        f"🔵 **ID của bạn là `{user_id}`**\n\n"
        f"🏛️ Tham gia Room TX để săn hũ và nhận giftcode hằng ngày https://t.me/tuanhung88chat\n\n"
        f"💙 Tham gia kênh thông báo để nhận code hàng ngày 💙"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=get_main_menu())

# --- XỬ LÝ ĐẶT CƯỢC & GỬI THÔNG BÁO VÀO NHÓM ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
        
    text = update.message.text.strip()
    user_id = update.effective_user.id
    user = get_user(user_id)

    parts = text.split()
    if len(parts) == 2 and parts[0].upper() in ["T", "X", "C", "L"]:
        choice = parts[0].upper()
        amount_str = parts[1].lower()
        
        if amount_str == "max":
            bet_amount = user["balance"]
            if user["is_newbie"] and bet_amount > 10000:
                bet_amount = 10000
        else:
            try:
                bet_amount = int(amount_str)
            except ValueError:
                return

        if bet_amount < 100:
            await update.message.reply_text("❌ Mức cược tối thiểu là `100 VNĐ`!", parse_mode="Markdown")
            return
        if bet_amount > 3000000:
            await update.message.reply_text("❌ Mức cược tối đa mỗi bên là `3.000.000 VNĐ`!", parse_mode="Markdown")
            return
        if user["is_newbie"] and bet_amount > 10000:
            await update.message.reply_text("⚠️ Bạn đang là Tân thủ (Giới hạn cược max 10k). Vui lòng nạp 50k để mở khóa toàn bộ hạn mức!", parse_mode="Markdown")
            return
        if user["balance"] < bet_amount:
            await update.message.reply_text("❌ Số dư tài khoản không đủ để đặt cược số tiền này!", parse_mode="Markdown")
            return

        user["balance"] -= bet_amount
        user["total_bet"] += bet_amount
        
        session_bets[choice] += bet_amount
        if user_id not in user_session_bets:
            user_session_bets[user_id] = {"T": 0, "X": 0, "C": 0, "L": 0}
        user_session_bets[user_id][choice] += bet_amount

        full_name_choice = {"T": "TÀI", "X": "XỈU", "C": "CHẮN", "L": "LẺ"}[choice]
        
        keyboard = [[InlineKeyboardButton("🐸 Ẩn Danh", callback_data="an_danh")]]
        await update.message.reply_text(
            f"🏆 **Đặt thành công phiên XX**\n"
            f"**#{current_session}**\n"
            f"{full_name_choice} `{bet_amount:,}` 🐸 **Ẩn Danh**",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        if GROUP_CHAT_ID:
            try:
                await context.bot.send_message(
                    chat_id=GROUP_CHAT_ID,
                    text=(
                        f"🏆 **Đặt thành công phiên XX**\n"
                        f"**#{current_session}**\n"
                        f"{choice} `{bet_amount:,}` 🐸 **Ẩn Danh (ID: {user_id})**"
                    ),
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        return

    if text == "📄 Tài khoản":
        update_vip(user)
        keyboard = [
            [InlineKeyboardButton("📈 LS nạp", callback_data="ls_nap"), InlineKeyboardButton("📉 LS rút", callback_data="ls_rut")],
            [InlineKeyboardButton("📊 LS chơi", callback_data="ls_choi"), InlineKeyboardButton("👑 VIP", callback_data="vip_info")],
            [InlineKeyboardButton("🎁 Nhập giftcode", callback_data="nhap_gc"), InlineKeyboardButton("🎫 Mua giftcode", callback_data="mua_gc")],
            [InlineKeyboardButton("💸 Hoàn cược ngày", callback_data="hc_ngay"), InlineKeyboardButton("💰 Hoàn cược tuần", callback_data="hc_tuan")],
            [InlineKeyboardButton("🛡️ Hoàn thua ngày", callback_data="ht_ngay"), InlineKeyboardButton("🛡️ Hoàn thua tuần", callback_data="ht_tuan")],
            [InlineKeyboardButton("🎧 Hỗ trợ", callback_data="ho_tro")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        info_text = (
            f"🏛️ **THÔNG TIN TÀI KHOẢN**\n"
            f"🆔 ID: `{user_id}`\n"
            f"🪙 Số dư hiện tại: `{user['balance']:,} VNĐ`\n"
            f"👑 Cấp Vip: `{user['vip_level']}` (Điểm: {user['vip_points']})\n"
            f"🔰 Cấp bậc: {'Tân thủ (Max cược 10k)' if user['is_newbie'] else 'Chính thức (Không giới hạn)'}\n\n"
            f"- Cược hôm nay: `{user['total_bet']:,}đ`\n"
            f"- Tổng cược: `{user['total_bet']:,}đ`"
        )
        await update.message.reply_text(info_text, parse_mode="Markdown", reply_markup=reply_markup)

    elif text == "💲 Nạp Tiền":
        keyboard = [
            [InlineKeyboardButton("20.000đ", callback_data="nap_20000"), InlineKeyboardButton("30.000đ", callback_data="nap_30000"), InlineKeyboardButton("50.000đ", callback_data="nap_50000")],
            [InlineKeyboardButton("100.000đ", callback_data="nap_100000"), InlineKeyboardButton("200.000đ", callback_data="nap_200000"), InlineKeyboardButton("500.000đ", callback_data="nap_500000")],
            [InlineKeyboardButton("1.000.000đ", callback_data="nap_1000000"), InlineKeyboardButton("2.000.000đ", callback_data="nap_2000000"), InlineKeyboardButton("5.000.000đ", callback_data="nap_5000000")],
            [InlineKeyboardButton("10.000.000đ", callback_data="nap_10000000"), InlineKeyboardButton("20.000.000đ", callback_data="nap_20000000"), InlineKeyboardButton("50.000.000đ", callback_data="nap_50000000")],
            [InlineKeyboardButton("🏦 Chuyển khoản ngân hàng (Khác)", callback_data="nap_nganhang")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        nap_text = (
            "✨ **HỆ THỐNG NẠP TIỀN TỰ ĐỘNG**\n\n"
            "✨ Hoặc bấm nút số tiền bên dưới để lấy nhanh thông tin.\n\n"
            "⚠️ **Lưu ý:**\n"
            "✅ Chuyển đúng **SỐ TIỀN** và **NỘI DUNG** được cung cấp.\n"
            "✅ Mỗi lần nạp cần lấy thông tin **MỚI** (Mã nạp hết hạn sau **10 phút**).\n"
            "🛑 Không dùng thông tin cũ cho giao dịch sau.\n"
            "📦 Nạp tối thiểu: **10.000đ**"
        )
        await update.message.reply_text(nap_text, parse_mode="Markdown", reply_markup=reply_markup)

    elif text == "📁 Danh sách game":
        game_text = (
            "🎮 **DANH SÁCH TRÒ CHƠI**\n"
            "Vô nhóm chơi: https://t.me/tuanhung88chat\n\n"
            "- **T**: Tổng 3 viên XX từ 11 - 18 Tài.\n"
            "- **X**: Tổng 3 viên XX từ 3 - 10 Xỉu.\n"
            "- **C**: Tổng 3 viên XX là Chẵn.\n"
            "- **L**: Tổng 3 viên XX là Lẻ.\n\n"
            "📌 **Tỷ lệ trả thưởng:**\n"
            "- T/X/C/L: x1.95\n"
            "👉 Tối thiểu 100 và tối đa mỗi bên 3.000.000\n\n"
            "📌 **Cách chơi:**\n"
            "• `T 20000` / `X 20000` / `C 20000` / `L 20000`\n"
            "• Cược max số dư/giới hạn: `T max` / `XX MAX`"
        )
        keyboard = [
            [InlineKeyboardButton("🔗 Tài Xỉu Room", url="https://t.me/tuanhung88chat")]
        ]
        await update.message.reply_text(game_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif text == "💳 Rút Tiền":
        if not user["bank_info"]:
            await update.message.reply_text(
                "⚠️ Bạn chưa cài đặt tài khoản ngân hàng nhận tiền!\n\n"
                "👉 Vui lòng sử dụng cú pháp để cài đặt:\n"
                "`/caidatbank [stk] [ngân_hàng] [tên_chủ_tài_khoản]`\n"
                "Ví dụ: `/caidatbank 9520252005 MB LUC THUY LINH`",
                parse_mode="Markdown"
            )
        else:
            rut_text = (
                "🧾 **THÔNG TIN RÚT TIỀN**\n\n"
                f"STK đã cài đặt của bạn:\n"
                f"`{user['bank_info']}`\n\n"
                "💸 Rút tiền về tài khoản trên:\n"
                "• `/rut [số tiền]` - VD: `/rut 50000`\n"
                "• `/rut all` - Rút tối đa phần khả dụng (đã trừ phí 1%)\n\n"
                "⚠️ Phí rút 1%. Rút tối thiểu 50.000đ."
            )
            await update.message.reply_text(rut_text, parse_mode="Markdown")

    elif text == "🌸 Chuyển Tiền":
        await update.message.reply_text("🌸 Cú pháp chuyển tiền: `/chuyentien [ID_nhận] [Số_tiền]`")

    elif text == "🚀 Dua top":
        await update.message.reply_text("🚀 **BẢNG XẾP HẠNG ĐUA TOP**\n1. Chưa có dữ liệu tuần này.")

    elif text == "🎁 Event":
        await update.message.reply_text("🎁 Nhận code miễn phí mỗi ngày tại kênh thông báo sự kiện.")

    elif text == "🔍 Lệnh":
        # HOÀN TOÀN SẠCH SẼ - CHỈ GIỮ LẠI CÁC LỆNH DÀNH CHO THÀNH VIÊN NGƯỜI CHƠI
        help_text = (
            "📜 **DANH SÁCH LỆNH**\n\n"
            "🎲 **Game Tài Xỉu:**\n"
            "• `T/X/C/L [tiền]` — Tài/Xỉu/Chẵn/Lẻ\n\n"
            "💰 **TÀI KHOẢN:**\n"
            "• `/nap [tiền]` — Nạp tiền\n"
            "• `/rut [tiền]` hoặc `/rut all` — Rút tiền\n"
            "• `/lsnap`, `/lsrut`, `/lschoi` — Lịch sử\n"
            "• `/caidatbank [stk] [mã_bank] [tên]` — Cài STK\n"
            "• `/chuyen [uid] [tiền]` — Chuyển tiền nội bộ\n\n"
            "🎁 **KHÁC:**\n"
            "• `/code [mã]` hoặc `/nhapcode [mã]` — Nhập giftcode\n"
            "• `/muagift [số_lượng] [mệnh_giá]` — Mua giftcode"
        )
        await update.message.reply_text(help_text, parse_mode="Markdown")

async def caidatbank_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("⚠️ Sai cú pháp! Dùng: `/caidatbank [stk] [ngân_hàng] [tên]`", parse_mode="Markdown")
        return
    user["bank_info"] = f"{args[0]} - {args[1].upper()} - {' '.join(args[2:]).upper()}"
    await update.message.reply_text(f"✅ Đã cài đặt STK thành công: `{user['bank_info']}`", parse_mode="Markdown")

async def rut_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    args = context.args
    if not user["bank_info"]:
        await update.message.reply_text("❌ Chưa cài STK! Dùng `/caidatbank` trước.")
        return
    if not args:
        await update.message.reply_text("⚠️ Dùng: `/rut [số_tiền]` hoặc `/rut all`")
        return
    try:
        rut_tien = user["balance"] if args[0].lower() == "all" else int(args[0])
    except ValueError:
        return
    if rut_tien < 50000 or rut_tien > user["balance"]:
        await update.message.reply_text("❌ Số tiền rút không hợp lệ hoặc vượt quá số dư!")
        return
    phi = int(rut_tien * 0.01)
    thuc_nhan = rut_tien - phi
    user["balance"] -= rut_tien
    user["history_rut"].append(f"Rút {rut_tien:,}đ về {user['bank_info']}")
    
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"🔔 **YÊU CẦU RÚT TIỀN**\n👤 ID người chơi: `{user_id}`\n💸 Số tiền rút: `{rut_tien:,}đ` (Thực nhận: `{thuc_nhan:,}đ`)\n🏦 STK: `{user['bank_info']}`",
                parse_mode="Markdown"
            )
        except Exception:
            pass

    if GROUP_CHAT_ID:
        try:
            await context.bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text=f"💳 **THÔNG BÁO RÚT TIỀN**\n👤 Người chơi ID: `{user_id}` vừa tạo lệnh rút thành công số tiền `{rut_tien:,} VNĐ`!",
                parse_mode="Markdown"
            )
        except Exception:
            pass

    await update.message.reply_text(f"✅ Gửi yêu cầu rút `{rut_tien:,}đ` thành công! Chờ Admin chuyển khoản.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global pending_nap
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data.startswith("nap_") and data != "nap_nganhang":
        amount = int(data.replace("nap_", ""))
        magd = random.randint(100000, 999999)
        pending_nap[str(magd)] = {"user_id": user_id, "amount": amount}
        
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"🔔 **MÃ NẠP MỚI**\n👤 ID: `{user_id}`\n💵 Số tiền: `{amount:,}đ`\n📝 Nội dung: `NAP{user_id}{magd}`\n🔑 Mã: `{magd}`\n👉 `/duyệt {magd}` | `/tuchoi {magd}`",
                    parse_mode="Markdown"
                )
            except Exception:
                pass

        if GROUP_CHAT_ID:
            try:
                await context.bot.send_message(
                    chat_id=GROUP_CHAT_ID,
                    text=f"💲 **THÔNG BÁO TẠO MÃ NẠP**\n👤 Người chơi ID: `{user_id}` vừa tạo mã nạp số tiền `{amount:,} VNĐ`!",
                    parse_mode="Markdown"
                )
            except Exception:
                pass

        keyboard = [[InlineKeyboardButton("🐸 Nạp tiền tại đây", url="https://t.me/tuanhung88chat")]]
        await query.message.reply_text(
            f"➕ **THÔNG TIN CHUYỂN KHOẢN NẠP {amount:,} VNĐ**\n\n"
            f"🏦 Ngân hàng: MBBANK\n"
            f"📌 STK: `0328122738`\n"
            f"💰 Chủ TK: LUC THUY LINH\n"
            f"💵 Số tiền: `{amount:,} VNĐ`\n"
            f"📝 Nội dung: `NAP{user_id}{magd}`\n\n"
            f"⏰ **Hạn mã nạp:** 10 phút (Quá hạn vui lòng lấy mã mới).\n"
            f"👉 Hệ thống sẽ tự động cộng tiền khi Admin duyệt!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif data == "ls_nap":
        u = get_user(user_id)
        await query.message.reply_text("\n".join(u["history_nap"]) if u["history_nap"] else "Chưa có lịch sử nạp.")
    elif data == "ls_rut":
        u = get_user(user_id)
        await query.message.reply_text("\n".join(u["history_rut"]) if u["history_rut"] else "Chưa có lịch sử rút.")
    elif data == "ls_choi":
        u = get_user(user_id)
        await query.message.reply_text("\n".join(u["history_choi"]) if u["history_choi"] else "Chưa có lịch sử chơi.")
    elif data == "vip_info":
        u = get_user(user_id)
        update_vip(u)
        await query.message.reply_text(f"👑 Cấp: {u['vip_level']} | Điểm: {u['vip_points']}")
    elif data == "nhap_gc":
        await query.message.reply_text("💡 Dùng cú pháp: `/code [Mã_code]` để nhận thưởng.")
    elif data == "mua_gc":
        await query.message.reply_text("🎫 Dùng cú pháp: `/muagift [số_lượng] [mệnh_giá]`")
    elif data == "hc_ngay":
        u = get_user(user_id)
        t = int(u["total_bet"] * 0.004)
        u["balance"] += t
        await query.message.reply_text(f"🎁 Nhận hoàn cược ngày thành công: `+{t:,}đ`", parse_mode="Markdown")
    elif data == "ho_tro":
        await query.message.reply_text("🎧 Hỗ trợ trực tuyến 24/7 qua CSKH.")
    elif data == "nap_nganhang":
        magd = random.randint(100000, 999999)
        pending_nap[str(magd)] = {"user_id": user_id, "amount": 50000}
        
        if GROUP_CHAT_ID:
            try:
                await context.bot.send_message(
                    chat_id=GROUP_CHAT_ID,
                    text=f"💲 **THÔNG BÁO TẠO MÃ NẠP**\n👤 Người chơi ID: `{user_id}` vừa tạo mã nạp số tiền `50,000 VNĐ`!",
                    parse_mode="Markdown"
                )
            except Exception:
                pass

        keyboard = [[InlineKeyboardButton("🐸 Nạp tiền tại đây", url="https://t.me/tuanhung88chat")]]
        await query.message.reply_text(
            f"➕ **THÔNG TIN CHUYỂN KHOẢN NẠP 50,000 VNĐ**\n\n"
            f"🏦 Ngân hàng: MBBANK | STK: `0328122738`\n"
            f"💰 Chủ TK: LUC THUY LINH\n"
            f"📝 Nội dung: `NAP{user_id}{magd}`\n"
            f"⏰ Hạn: 10 phút.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# --- VÒNG LẶP PHIÊN TÀI XỈU TỰ ĐỘNG ---
async def run_taixiu_loop(application):
    global current_session, session_bets, user_session_bets, huvang_pool, forced_dice_result, history_sessions
    
    while True:
        try:
            session_bets = {"T": 0, "X": 0, "C": 0, "L": 0}
            user_session_bets = {}
            
            target_chat = GROUP_CHAT_ID if GROUP_CHAT_ID else -1004222063034
            
            start_text = (
                f"🐸 **ET88 - TUNG XX** 🎲\n"
                f"🔥 **Xin mời đặt cược phiên XX**\n"
                f"**#{current_session}** 🔥\n\n"
                f"💲 **Min: 100 | Max mỗi bên: 3.000.000**\n\n"
                f"🎯 **Cách chơi: [Cửa cược] [số tiền]**\n"
                f"🔵 Tài: T | 🔴 Xỉu: X | ⚪ Chẵn: C | ⚫ Lẻ: L\n"
                f"🐸 Ẩn danh thưởng: TT/XX/CC/LL\n"
                f"🔥 T2/X2/C2/L2 trả x2.3\n"
                f"💎 Xiên TC/CT/TL/LT trả x3"
            )
            keyboard_start = [[InlineKeyboardButton("🐸 Vào bot chơi", url="https://t.me/tuanhung88_bot")]]
            
            if target_chat:
                await application.bot.send_message(chat_id=target_chat, text=start_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard_start))
            
            await asyncio.sleep(20)
            
            if target_chat:
                await application.bot.send_message(
                    chat_id=target_chat,
                    text=f"🐸 **Còn 40 giây phiên #{current_session}**\n🔵 **TÀI**: {session_bets['T']:,}\n🔴 **XỈU**: {session_bets['X']:,}\n\n⚪ **CHẮN**: {session_bets['C']:,}\n⚫ **LẺ**: {session_bets['L']:,}",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🐸 Nạp tiền tại đây", url="https://t.me/tuanhung88_bot")]])
                )
            await asyncio.sleep(20)
            
            if target_chat:
                await application.bot.send_message(
                    chat_id=target_chat,
                    text=f"🐸 **Còn 20 giây phiên #{current_session}**\n🔵 **TÀI**: {session_bets['T']:,}\n🔴 **XỈU**: {session_bets['X']:,}\n\n⚪ **CHẮN**: {session_bets['C']:,}\n⚫ **LẺ**: {session_bets['L']:,}",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🐸 Nạp tiền tại đây", url="https://t.me/tuanhung88_bot")]])
                )
            await asyncio.sleep(10)
            
            if target_chat:
                await application.bot.send_message(
                    chat_id=target_chat,
                    text=f"🐸 **Còn 10 giây phiên #{current_session}**\n🔵 **TÀI**: {session_bets['T']:,}\n🔴 **XỈU**: {session_bets['X']:,}\n\n⚪ **CHẮN**: {session_bets['C']:,}\n⚫ **LẺ**: {session_bets['L']:,}",
                    parse_mode="Markdown"
                )
            await asyncio.sleep(10)
            
            if target_chat:
                await application.bot.send_message(chat_id=target_chat, text=f"🤖 **Hết thời gian đặt cược phiên #{current_session}**", parse_mode="Markdown")
                await application.bot.send_message(chat_id=target_chat, text=f"🤖 **Bắt đầu tung XX phiên #{current_session}**", parse_mode="Markdown")
            
            if forced_dice_result == "TAI":
                dices = (5, 5, 6)
            elif forced_dice_result == "XIU":
                dices = (1, 2, 3)
            else:
                dices = (random.randint(1, 6), random.randint(1, 6), random.randint(1, 6))
            
            forced_dice_result = None
            
            if target_chat:
                for d in dices:
                    await application.bot.send_dice(chat_id=target_chat, emoji="🎲")
                    await asyncio.sleep(1)
            
            tong = sum(dices)
            ket_qua_tx = "TÀI" if tong >= 11 else "XỈU"
            ket_qua_cl = "CHẮN" if tong % 2 == 0 else "LẺ"
            
            icon_tx = "🔵" if ket_qua_tx == "TÀI" else "🔴"
            icon_cl = "⚪" if ket_qua_cl == "CHẮN" else "⚫"
            
            history_sessions.append((icon_tx, icon_cl))
            if len(history_sessions) > 12:
                history_sessions.pop(0)
                
            history_str = "".join([f"{tx}{cl}" for tx, cl in history_sessions])
            
            tong_thang = 0
            tong_thua = 0
            
            for u_id, bets in user_session_bets.items():
                u = get_user(u_id)
                thang_user = 0
                thua_user = 0
                
                if bets["T"] > 0 and ket_qua_tx == "TÀI":
                    thuong = int(bets["T"] * 1.95)
                    thang_user += thuong
                    u["balance"] += thuong
                elif bets["T"] > 0:
                    thua_user += bets["T"]
                    
                if bets["X"] > 0 and ket_qua_tx == "XỈU":
                    thuong = int(bets["X"] * 1.95)
                    thang_user += thuong
                    u["balance"] += thuong
                elif bets["X"] > 0:
                    thua_user += bets["X"]
                    
                if bets["C"] > 0 and ket_qua_cl == "CHẮN":
                    thuong = int(bets["C"] * 1.95)
                    thang_user += thuong
                    u["balance"] += thuong
                elif bets["C"] > 0:
                    thua_user += bets["C"]
                    
                if bets["L"] > 0 and ket_qua_cl == "LẺ":
                    thuong = int(bets["L"] * 1.95)
                    thang_user += thuong
                    u["balance"] += thuong
                elif bets["L"] > 0:
                    thua_user += bets["L"]
                    
                tong_thang += thang_user
                tong_thua += thua_user
                if thang_user > 0 or thua_user > 0:
                    u["history_choi"].append(f"Phiên #{current_session}: Thắng +{thang_user:,}đ")

            huvang_pool += random.randint(100, 500)
            
            ket_qua_msg = (
                f"┌─────────────────────────\n"
                f"│ **{dices[0]} {dices[1]} {dices[2]}** 🔵 **{ket_qua_tx} {ket_qua_cl}** {icon_tx} {icon_cl}\n"
                f"│ 🟠 **Tổng điểm xúc xắc: {tong}**\n"
                f"│ (3-18)\n"
                f"│\n"
                f"│ ｜ **Tổng thắng: {tong_thang:,}**\n"
                f"│ ｜ **Tổng thua: {tong_thua:,}**\n"
                f"│ ｜ **Công hũ: +{random.randint(50, 999)}**\n"
                f"│ ｜ **Hũ hiện tại: {huvang_pool:,}**\n"
                f"└─────────────────────────\n\n"
                f"💬 **Thống kê 12 phiên gần nhất:**\n"
                f"{history_str}"
            )
            
            if target_chat:
                keyboard_kq = [
                    [InlineKeyboardButton("💲 Nạp tiền", url="https://t.me/tuanhung88_bot"), InlineKeyboardButton("📜 Lịch sử phiên", url="https://t.me/tuanhung88_bot")]
                ]
                await application.bot.send_message(
                    chat_id=target_chat,
                    text=f"🎉 **Kết quả XX phiên #{current_session}**\n\n{ket_qua_msg}",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard_kq)
                )
            
            current_session += 1
            
        except Exception as e:
            logging.error(f"Lỗi vòng lặp phiên: {e}")
            await asyncio.sleep(5)

# --- QUẢN TRỊ ADMIN ---
async def duyet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    args = context.args
    if not args:
        return
    ma_gd = args[0]
    if ma_gd in pending_nap:
        info = pending_nap[ma_gd]
        u = get_user(info["user_id"])
        u["is_newbie"] = False
        u["balance"] += info["amount"]
        u["history_nap"].append(f"Nạp thành công {info['amount']:,}đ")
        del pending_nap[ma_gd]
        
        try:
            await context.bot.send_message(chat_id=info["user_id"], text=f"✅ **NẠP TIỀN THÀNH CÔNG!**\nCộng `+{info['amount']:,} VNĐ` vào số dư.", parse_mode="Markdown")
        except Exception:
            pass
        await update.message.reply_text(f"✅ Đã duyệt mã nạp #{ma_gd} thành công!")

async def tuchoi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    args = context.args
    if not args:
        return
    ma_gd = args[0]
    if ma_gd in pending_nap:
        del pending_nap[ma_gd]
        await update.message.reply_text(f"❌ Đã từ chối mã #{ma_gd}.")

async def chinhxucxac_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global forced_dice_result
    if update.effective_user.id not in ADMIN_IDS:
        return
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Dùng: `/chinhxucxac tai` hoặc `/chinhxucxac xiu` hoặc `/chinhxucxac reset`")
        return
    mode = args[0].lower()
    if mode == "tai":
        forced_dice_result = "TAI"
        await update.message.reply_text("⚡ Đã khóa 100% ra TÀI phiên sau!")
    elif mode == "xiu":
        forced_dice_result = "XIU"
        await update.message.reply_text("⚡ Đã khóa 100% ra XỈU phiên sau!")
    else:
        forced_dice_result = None
        await update.message.reply_text("🔄 Đã reset xúc xắc ngẫu nhiên.")

# --- KHỞI CHẠY CHÍNH ---
TOKEN = "9286450426:AAHYoubtmQirYbLnmmN309OeA81sABUrxsA"

async def main_async():
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("caidatbank", caidatbank_command))
    application.add_handler(CommandHandler("rut", rut_command))
    application.add_handler(CommandHandler("duyet", duyet_command))
    application.add_handler(CommandHandler("tuchoi", tuchoi_command))
    application.add_handler(CommandHandler("chinhxucxac", chinhxucxac_command))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    
    asyncio.create_task(run_taixiu_loop(application))
    
    stop_signal = asyncio.get_running_loop().create_future()
    await stop_signal

def main():
    try:
        asyncio.run(main_async())
    except (KeyboardInterrupt, SystemExit):
        pass

if __name__ == "__main__":
    main()
