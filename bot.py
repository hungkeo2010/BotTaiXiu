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
users_db = {}       
giftcode_db = {}    
pending_nap = {}    

# ID Admin chính thức
ADMIN_IDS = [8682451039]

# --- QUAN TRỌNG: ĐIỀN CHAT ID CỦA NHÓM VÀO ĐÂY (VD: -1001234567890) ---
GROUP_CHAT_ID = None  

# Biến toàn cục quản lý phiên Tài Xỉu
forced_dice_result = None
current_session = 199580
huvang_pool = 287500
session_bets = {"T": 0, "X": 0, "C": 0, "L": 0}
user_session_bets = {}  
history_sessions = [] 
loop_started = False  

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

# --- XỬ LÝ ĐẶT CƯỢC ---
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

        await update.message.reply_text(
            f"🌟 **Đặt thành công phiên XX #{current_session}**\n"
            f"{choice} {bet_amount:,}\n"
            f"Số dư sau khi cược: {user['balance']:,}",
            parse_mode="Markdown"
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
            "- **T**: Tổng 3 viên XX từ 11 - 18 Tài[span_2](start_span)[span_2](end_span).\n"
            "- **X**: Tổng 3 viên XX từ 3 - 10 Xỉu[span_3](start_span)[span_3](end_span).\n"
            "- **C**: Tổng 3 viên XX là Chẵn[span_4](start_span)[span_4](end_span).\n"
            "- **L**: Tổng 3 viên XX là Lẻ[span_5](start_span)[span_5](end_span).\n\n"
            "📌 **Tỷ lệ trả thưởng:**\n"
            "- T/X/C/L: x1.95\n"
            "👉 Tối thiểu 100 và tối đa mỗi bên 3.000.000"
        )
        keyboard = [
            [InlineKeyboardButton("🔗 Tài Xỉu Room", url="https://t.me/tuanhung88chat")]
        ]
        await update.message.reply_text(game_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif text == "💳 Rút Tiền":
        if not user["bank_info"]:
            await update.message.reply_text(
                "⚠️ Bạn chưa cài đặt tài khoản ngân hàng nhận tiền!\n\n"
                "👉 Dùng cú pháp: `/caidatbank [stk] [ngân_hàng] [tên]`",
                parse_mode="Markdown"
            )
        else:
            rut_text = (
                "🧾 **THÔNG TIN RÚT TIỀN**\n\n"
                f"STK: `{user['bank_info']}`\n\n"
                "💸 Rút tiền: `/rut [số_tiền]` hoặc `/rut all`"
            )
            await update.message.reply_text(rut_text, parse_mode="Markdown")

    elif text == "🌸 Chuyển Tiền":
        await update.message.reply_text("🌸 Cú pháp chuyển tiền: `/chuyentien [ID_nhận] [Số_tiền]`")

    elif text == "🚀 Dua top":
        await update.message.reply_text("🚀 **BẢNG XẾP HẠNG ĐUA TOP**\n1. Chưa có dữ liệu tuần này.")

    elif text == "🎁 Event":
        await update.message.reply_text("🎁 Nhận code miễn phí mỗi ngày tại kênh thông báo sự kiện.")

    elif text == "🔍 Lệnh":
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
        await update.message.reply_text("⚠️ Dùng: `/caidatbank [stk] [ngân_hàng] [tên]`", parse_mode="Markdown")
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
            await context.bot.send_message(chat_id=admin_id, text=f"🔔 **RÚT TIỀN**\nID: `{user_id}`\nSố tiền: `{rut_tien:,}đ`", parse_mode="Markdown")
        except Exception:
            pass

    await update.message.reply_text(f"✅ Gửi yêu cầu rút `{rut_tien:,}đ` thành công!")

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
                await context.bot.send_message(chat_id=admin_id, text=f"🔔 **MÃ NẠP MỚI**\nID: `{user_id}`\nTiền: `{amount:,}đ`\nMã: `{magd}`\n👉 `/duyệt {magd}`", parse_mode="Markdown")
            except Exception:
                pass

        keyboard = [[InlineKeyboardButton("🐸 Nạp tiền tại đây", url="https://t.me/tuanhung88chat")]]
        await query.message.reply_text(
            f"➕ **THÔNG TIN NẠP {amount:,} VNĐ**\nMBBANK | STK: `0328122738`\nNội dung: `NAP{user_id}{magd}`",
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
        await query.message.reply_text("💡 Dùng cú pháp: `/code [Mã_code]`")
    elif data == "mua_gc":
        await query.message.reply_text("🎫 Dùng cú pháp: `/muagift [số_lượng] [mệnh_giá]`")
    elif data == "hc_ngay":
        u = get_user(user_id)
        t = int(u["total_bet"] * 0.004)
        u["balance"] += t
        await query.message.reply_text(f"🎁 Nhận hoàn cược: `+{t:,}đ`", parse_mode="Markdown")
    elif data == "ho_tro":
        await query.message.reply_text("🎧 Hỗ trợ 24/7.")
    elif data == "nap_nganhang":
        magd = random.randint(100000, 999999)
        pending_nap[str(magd)] = {"user_id": user_id, "amount": 50000}
        keyboard = [[InlineKeyboardButton("🐸 Nạp tiền tại đây", url="https://t.me/tuanhung88chat")]]
        await query.message.reply_text(
            f"➕ **THÔNG TIN NẠP 50,000 VNĐ**\nMBBANK | STK: `0328122738`\nNội dung: `NAP{user_id}{magd}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# --- VÒNG LẶP PHIÊN TÀI XỈU ---
async def run_taixiu_loop(application):
    global current_session, session_bets, user_session_bets, huvang_pool, forced_dice_result, history_sessions
    
    while True:
        try:
            session_bets = {"T": 0, "X": 0, "C": 0, "L": 0}
            user_session_bets = {}
            
            target_chat = GROUP_CHAT_ID if GROUP_CHAT_ID else -1004222063034
            
            start_text = (
                f"🐸 **TuanHung88 - TUNG XX** 🎲\n"
                f"🔥 **Xin mời đặt cược phiên XX**\n"
                f"**#{current_session}** 🔥\n\n"
                f"💲 **Min: 100 | Max mỗi bên: 3.000.000**\n\n"
                f"🎯 **Cách chơi: [Cửa cược] [số tiền]**\n"
                f"🔵 Tài: T | 🔴 Xỉu: X | ⚪ Chẵn: C | ⚫ Lẻ: L"
            )
            keyboard_start = [[InlineKeyboardButton("🐸 Vào bot chơi", url="https://t.me/tuanhung88_bot")]]
            
            if target_chat:
                await application.bot.send_message(chat_id=target_chat, text=start_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard_start))
            
            await asyncio.sleep(20)
            if target_chat:
                await application.bot.send_message(chat_id=target_chat, text=f"🐸 **Còn 40 giây phiên #{current_session}**\n🔵 **TÀI**: {session_bets['T']:,}\n🔴 **XỈU**: {session_bets['X']:,}", parse_mode="Markdown")
            await asyncio.sleep(20)
            if target_chat:
                await application.bot.send_message(chat_id=target_chat, text=f"🐸 **Còn 20 giây phiên #{current_session}**\n🔵 **TÀI**: {session_bets['T']:,}\n🔴 **XỈU**: {session_bets['X']:,}", parse_mode="Markdown")
            await asyncio.sleep(10)
            if target_chat:
                await application.bot.send_message(chat_id=target_chat, text=f"🐸 **Còn 10 giây phiên #{current_session}**", parse_mode="Markdown")
            await asyncio.sleep(10)
            
            if target_chat:
                await application.bot.send_message(chat_id=target_chat, text=f"🤖 **Hết thời gian đặt cược phiên #{current_session}**", parse_mode="Markdown")
                await application.bot.send_message(chat_id=target_chat, text=f"🤖 **Bắt đầu tung XX phiên #{current_session}**", parse_mode="Markdown")
            
            # --- XỬ LÝ KẾT QUẢ XÚC XẮC & LỆNH ÉP (ADMIN) ---
            if forced_dice_result == "TAI":
                # Ép Tài: Tổng điểm từ 11 đến 18
                dices = (5, 5, 3)
            elif forced_dice_result == "XIU":
                # Ép Xỉu: Tổng điểm từ 3 đến 10
                dices = (1, 2, 3)
            else:
                dices = (random.randint(1, 6), random.randint(1, 6), random.randint(1, 6))
            
            forced_dice_result = None
            
            if target_chat:
                for _ in range(3):
                    await application.bot.send_dice(chat_id=target_chat, emoji="🎲")
                    await asyncio.sleep(1.2)
            
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
                
                if bets["T"] > 0:
                    if ket_qua_tx == "TÀI":
                        thuong = int(bets["T"] * 1.95)
                        thang_user += thuong
                        u["balance"] += thuong
                        try:
                            await application.bot.send_message(chat_id=u_id, text=f"✅ **Thắng phiên #{current_session}**\nCược TÀI - {bets['T']:,}\nTiền nhận: {thuong:,}\nSố dư mới: {u['balance']:,}", parse_mode="Markdown")
                        except Exception:
                            pass
                    else:
                        thua_user += bets["T"]
                        try:
                            await application.bot.send_message(chat_id=u_id, text=f"❌ **Thua phiên #{current_session}**\nCược TÀI - {bets['T']:,}\nTiền nhận: 0\nSố dư mới: {u['balance']:,}", parse_mode="Markdown")
                        except Exception:
                            pass

                if bets["X"] > 0:
                    if ket_qua_tx == "XỈU":
                        thuong = int(bets["X"] * 1.95)
                        thang_user += thuong
                        u["balance"] += thuong
                        try:
                            await application.bot.send_message(chat_id=u_id, text=f"✅ **Thắng phiên #{current_session}**\nCược XỈU - {bets['X']:,}\nTiền nhận: {thuong:,}\nSố dư mới: {u['balance']:,}", parse_mode="Markdown")
                        except Exception:
                            pass
                    else:
                        thua_user += bets["X"]
                        try:
                            await application.bot.send_message(chat_id=u_id, text=f"❌ **Thua phiên #{current_session}**\nCược XỈU - {bets['X']:,}\nTiền nhận: 0\nSố dư mới: {u['balance']:,}", parse_mode="Markdown")
                        except Exception:
                            pass

                if bets["C"] > 0:
                    if ket_qua_cl == "CHẮN":
                        thuong = int(bets["C"] * 1.95)
                        thang_user += thuong
                        u["balance"] += thuong
                        try:
                            await application.bot.send_message(chat_id=u_id, text=f"✅ **Thắng phiên #{current_session}**\nCược CHẮN - {bets['C']:,}\nTiền nhận: {thuong:,}\nSố dư mới: {u['balance']:,}", parse_mode="Markdown")
                        except Exception:
                            pass
                    else:
                        thua_user += bets["C"]
                        try:
                            await application.bot.send_message(chat_id=u_id, text=f"❌ **Thua phiên #{current_session}**\nCược CHẮN - {bets['C']:,}\nTiền nhận: 0\nSố dư mới: {u['balance']:,}", parse_mode="Markdown")
                        except Exception:
                            pass

                if bets["L"] > 0:
                    if ket_qua_cl == "LẺ":
                        thuong = int(bets["L"] * 1.95)
                        thang_user += thuong
                        u["balance"] += thuong
                        try:
                            await application.bot.send_message(chat_id=u_id, text=f"✅ **Thắng phiên #{current_session}**\nCược LẺ - {bets['L']:,}\nTiền nhận: {thuong:,}\nSố dư mới: {u['balance']:,}", parse_mode="Markdown")
                        except Exception:
                            pass
                    else:
                        thua_user += bets["L"]
                        try:
                            await application.bot.send_message(chat_id=u_id, text=f"❌ **Thua phiên #{current_session}**\nCược LẺ - {bets['L']:,}\nTiền nhận: 0\nSố dư mới: {u['balance']:,}", parse_mode="Markdown")
                        except Exception:
                            pass
                    
                tong_thang += thang_user
                tong_thua += thua_user

            huvang_pool += random.randint(100, 500)
            
            ket_qua_msg = (
                f"┌─────────────────────────\n"
                f"│ **{dices[0]} {dices[1]} {dices[2]}** {icon_tx} **{ket_qua_tx} {ket_qua_cl}** {icon_tx} {icon_cl}\n"
                f"│ 🟠 **Tổng điểm xúc xắc: {tong}**\n"
                f"│ (3-18)\n"
                f"│\n"
                f"│ ｜ **Tổng thắng: {tong_thang:,}**\n"
                f"│ ｜ **Tổng thua: {tong_thua:,}**\n"
                f"│ ｜ **Công hũ: +{random.randint(50, 999)}**\n"
                f"│ ｜ **Hũ hiện tại: {huvang_pool:,}**\n"
                f"└─────────────────────────\n\n"
                f"💬 **Thống kê {len(history_sessions)} phiên gần nhất:**\n"
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
            await context.bot.send_message(chat_id=info["user_id"], text=f"✅ **NẠP THÀNH CÔNG!**\nCộng `+{info['amount']:,}đ`", parse_mode="Markdown")
        except Exception:
            pass
        await update.message.reply_text(f"✅ Đã duyệt mã #{ma_gd} thành công!")

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

async def taocode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    args = context.args
    if len(args) < 2:
        return
    try:
        soluong, tien = int(args[0]), int(args[1])
    except ValueError:
        return
    codes = []
    for _ in range(soluong):
        c = f"HIT{random.randint(100000, 999999)}"
        giftcode_db[c] = tien
        codes.append(c)
    await update.message.reply_text(f"✅ Tạo thành công {soluong} mã:\n`" + "\n".join(codes) + "`", parse_mode="Markdown")

async def themcode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    args = context.args
    if len(args) < 2:
        return
    code, tien = args[0], int(args[1])
    giftcode_db[code] = tien
    await update.message.reply_text(f"✅ Đã thêm mã `{code}` trị giá `{tien:,}đ`!", parse_mode="Markdown")

async def xoacode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    args = context.args
    if not args:
        return
    code = args[0]
    if code in giftcode_db:
        del giftcode_db[code]
        await update.message.reply_text(f"🗑️ Đã xóa mã `{code}`.")

async def danhsachcode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not giftcode_db:
        await update.message.reply_text("📂 Kho giftcode trống.")
        return
    list_str = "\n".join([f"• `{k}`: {v:,}đ" for k, v in giftcode_db.items()])
    await update.message.reply_text(f"📂 **KHO GIFTCODE:**\n{list_str}", parse_mode="Markdown")

async def code_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not args:
        return
    code = args[0]
    if code in giftcode_db:
        val = giftcode_db[code]
        user["balance"] += val
        del giftcode_db[code]
        await update.message.reply_text(f"🎉 **NHẬP CODE THÀNH CÔNG!**\n🎁 Nhận: `+{val:,} VNĐ`", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Mã code không tồn tại hoặc đã được sử dụng!")

async def muagift_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    user_id = update.effective_user.id
    user = get_user(user_id)
    if len(args) < 2:
        return
    try:
        soluong, menh_gia = int(args[0]), int(args[1])
    except ValueError:
        return
    available_codes = [code for code, val in giftcode_db.items() if val == menh_gia]
    if len(available_codes) < soluong:
        await update.message.reply_text(f"❌ Kho chỉ còn {len(available_codes)} mã mệnh giá {menh_gia:,}đ.")
        return
    tong_thanh_toan = int((soluong * menh_gia) * 1.05)
    if user["balance"] < tong_thanh_toan:
        await update.message.reply_text(f"❌ Không đủ số dư! Cần `{tong_thanh_toan:,}đ` (gồm 5% phí).")
        return
    user["balance"] -= tong_thanh_toan
    bought_codes = []
    for _ in range(soluong):
        c = available_codes.pop(0)
        del giftcode_db[c]
        bought_codes.append(c)
    await update.message.reply_text(f"✅ **MUA THÀNH CÔNG!**\nMã của bạn: `" + ", ".join(bought_codes) + "`", parse_mode="Markdown")

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

# --- KHỞI CHẠY CHÍNH (ĐÃ SỬA LỖI EVENT LOOP) ---
TOKEN = "9286450426:AAHYoubtmQirYbLnmmN309OeA81sABUrxsA"

async def post_init(application):
    global loop_started
    if not loop_started:
        loop_started = True
        asyncio.create_task(run_taixiu_loop(application))

def main():
    application = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("caidatbank", caidatbank_command))
    application.add_handler(CommandHandler("rut", rut_command))
    application.add_handler(CommandHandler("duyet", duyet_command))
    application.add_handler(CommandHandler("tuchoi", tuchoi_command))
    application.add_handler(CommandHandler("taocode", taocode_command))
    application.add_handler(CommandHandler("themcode", themcode_command))
    application.add_handler(CommandHandler("xoacode", xoacode_command))
    application.add_handler(CommandHandler("danhsachcode", danhsachcode_command))
    application.add_handler(CommandHandler("muagift", muagift_command))
    application.add_handler(CommandHandler("code", code_command))
    application.add_handler(CommandHandler("nhapcode", code_command))
    application.add_handler(CommandHandler("chinhxucxac", chinhxucxac_command))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
