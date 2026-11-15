import logging
import random
import asyncio
import json
import os
import threading
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- TẠO WEB SERVER BẰNG FLASK ĐỂ UPTIMEROBOT NHẬN DIỆN 200 OK ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is alive and running 24/7!", 200

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web_server, daemon=True).start()

# --- QUẢN LÝ DỮ LIỆU BỀN VỮNG (LƯU RA FILE JSON) ---
DB_FILE = "database.json"

def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {int(k): v for k, v in data.items()}
        except Exception as e:
            logging.error(f"Lỗi đọc database: {e}")
    return {}

def save_data():
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(users_db, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Lỗi lưu database: {e}")

# --- DỮ LIỆU HỆ THỐNG ---
users_db = load_data()       
giftcode_db = {}    
pending_nap = {}    
pending_rut = {}    

# ID Admin chính thức
ADMIN_IDS = [8682451039]
GROUP_CHAT_ID = -1004222063034  

# Biến toàn cục quản lý phiên Tài Xỉu
forced_dice_result = None
current_session = 200598
huvang_pool = 295000
session_bets = {"T": 0, "X": 0, "C": 0, "L": 0}
user_session_bets = {}  
user_session_total_bet = {} 
history_sessions = [] 
is_betting_open = False  
lucky_number = 79        
lucky_reward = 50000     

is_loop_running = False  

def get_user(user_id):
    if user_id not in users_db:
        users_db[user_id] = {
            "balance": 0,
            "total_bet": 0,
            "required_turnover": 0,
            "vip_points": 0,
            "vip_level": "Đồng 🥉",
            "is_newbie": True,  
            "has_received_x2": False,
            "bank_info": None,  
            "history_nap": [],
            "history_rut": [],
            "history_choi": []
        }
        save_data()
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
        f"🎁 **QUY ĐỊNH NẠP & RÚT:**\n"
        f"• **Nạp lần đầu:** X2 số tiền (Yêu cầu vòng cược **x4** mới được rút)\n"
        f"• **Nạp từ lần 2:** Yêu cầu vòng cược **x2** mới được rút\n\n"
        f"🏛️ Tham gia Room TX để săn hũ và nhận giftcode hằng ngày https://t.me/tuanhung88chat"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=get_main_menu())

async def sodu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    await update.message.reply_text(
        f"🪙 Số dư : `{user['balance']:,} VNĐ`",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_betting_open
    if not update.message or not update.message.text:
        return
        
    text = update.message.text.strip()
    user_id = update.effective_user.id
    user = get_user(user_id)

    parts = text.split()
    if len(parts) == 2 and parts[0].upper() in ["T", "X", "C", "L"]:
        if not is_betting_open:
            await update.message.reply_text("❌ Đã hết thời gian đặt cược cho phiên này! Vui lòng chờ phiên sau.", parse_mode="Markdown")
            return

        choice = parts[0].upper()
        amount_str = parts[1].lower()

        if user_id in user_session_bets:
            current_user_bets = user_session_bets[user_id]
            if choice == "T" and current_user_bets.get("X", 0) > 0:
                await update.message.reply_text("❌ Bạn đã đặt cửa XỈU rồi, không thể đặt thêm TÀI trong phiên này!", parse_mode="Markdown")
                return
            if choice == "X" and current_user_bets.get("T", 0) > 0:
                await update.message.reply_text("❌ Bạn đã đặt cửa TÀI rồi, không thể đặt thêm XỈU trong phiên này!", parse_mode="Markdown")
                return
            if choice == "C" and current_user_bets.get("L", 0) > 0:
                await update.message.reply_text("❌ Bạn đã đặt cửa LẺ rồi, không thể đặt thêm CHẴN trong phiên này!", parse_mode="Markdown")
                return
            if choice == "L" and current_user_bets.get("C", 0) > 0:
                await update.message.reply_text("❌ Bạn đã đặt cửa CHẴN rồi, không thể đặt thêm LẺ trong phiên này!", parse_mode="Markdown")
                return

        if amount_str in ["max", "all"]:
            bet_amount = user["balance"]
            if user["is_newbie"] and bet_amount > 10000:
                bet_amount = 10000
        else:
            try:
                cleaned_amount = amount_str.replace(",", "").replace(".", "")
                if cleaned_amount.endswith("k"):
                    bet_amount = int(cleaned_amount[:-1]) * 1000
                elif cleaned_amount.endswith("m"):
                    bet_amount = int(cleaned_amount[:-1]) * 1000000
                else:
                    bet_amount = int(cleaned_amount)
            except ValueError:
                return

        if bet_amount < 100:
            await update.message.reply_text("❌ Mức cược tối thiểu là `100 VNĐ`!", parse_mode="Markdown")
            return
            
        if session_bets[choice] >= 3000000:
            await update.message.reply_text(f"❌ Cửa này đã đạt mức tối đa `3.000.000 VNĐ` (Max 3m). Không nhận thêm cược!", parse_mode="Markdown")
            return
            
        if session_bets[choice] + bet_amount > 3000000:
            allowed_max = 3000000 - session_bets[choice]
            await update.message.reply_text(f"❌ Cửa này đã gần đạt mốc 3M! Bạn chỉ có thể đặt tối đa thêm `{allowed_max:,} VNĐ`.", parse_mode="Markdown")
            return

        if user["is_newbie"] and bet_amount > 10000:
            await update.message.reply_text("⚠️ Bạn đang là Tân thủ (Giới hạn cược max 10k). Vui lòng nạp tiền hoặc nhờ Admin mở khóa!", parse_mode="Markdown")
            return
        if user["balance"] < bet_amount:
            await update.message.reply_text("❌ Số dư tài khoản không đủ để đặt cược số tiền này!", parse_mode="Markdown")
            return

        user["balance"] -= bet_amount
        user["total_bet"] += bet_amount
        save_data()  
        
        session_bets[choice] += bet_amount
        if user_id not in user_session_bets:
            user_session_bets[user_id] = {"T": 0, "X": 0, "C": 0, "L": 0}
        user_session_bets[user_id][choice] += bet_amount

        user_session_total_bet[user_id] = user_session_total_bet.get(user_id, 0) + bet_amount

        chat_type = update.message.chat.type

        if chat_type in ["group", "supergroup"]:
            await update.message.reply_text(
                f"🌟 **Đặt thành công phiên XX**\n"
                f"**#{current_session}**\n"
                f"{choice} {bet_amount:,}\n"
                f"Số dư sau khi cược: {user['balance']:,}",
                parse_mode="Markdown"
            )
        else:
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
        
        x2_status = "Đã sử dụng ✅" if user.get("has_received_x2", False) else "Chưa sử dụng (Được X2 lần nạp đầu) 🔥"
        req_turnover = user.get("required_turnover", 0)
        current_total_bet = user["total_bet"]
        
        info_text = (
            f"🏛️ **THÔNG TIN TÀI KHOẢN**\n"
            f"🆔 ID: `{user_id}`\n"
            f"🪙 Số dư hiện tại: `{user['balance']:,} VNĐ`\n"
            f"🎁 Khuyến mãi Nạp X2: `{x2_status}`\n"
            f"📊 Vòng cược yêu cầu để rút: `{current_total_bet:,} / {req_turnover:,}đ`\n"
            f"👑 Cấp Vip: `{user['vip_level']}` (Điểm: {user['vip_points']})\n"
            f"🔰 Cấp bậc: {'Tân thủ (Max cược 10k)' if user['is_newbie'] else 'Chính thức (Không giới hạn)'}\n\n"
            f"- Tổng cược tích lũy: `{current_total_bet:,}đ`"
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
        
        x2_notice = "🎁 **ĐẶC QUYỀN:** Nạp lần đầu X2 tiền và yêu cầu vòng cược x4 mới được rút!" if not user.get("has_received_x2", False) else "🎁 Nạp từ lần 2: Yêu cầu vòng cược x2 số tiền nạp để rút."
        nap_text = (
            "✨ **HỆ THỐNG NẠP TIỀN TỰ ĐỘNG**\n\n"
            f"{x2_notice}\n\n"
            "✨ Hoặc bấm nút số tiền bên dưới để lấy nhanh thông tin.\n\n"
            "⚠️ **Lưu ý:**\n"
            "✅ Chuyển đúng **SỐ TIỀN** và **NỘI DUNG** được cung cấp.\n"
            "✅ Mỗi lần nạp cần lấy thông tin **MỚI** (Mã nạp hết hạn sau **10 phút**).\n"
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
                "💸 Rút tiền: `/rut [số_tiền]` hoặc `/rut all`\n"
                "📌 **Hạn mức rút:** Min `100.000đ` - Max `10.000.000đ`"
            )
            await update.message.reply_text(rut_text, parse_mode="Markdown")

    elif text == "🌸 Chuyển Tiền":
        await update.message.reply_text("🌸 Cú pháp chuyển tiền: `/chuyentien [ID_nhận] [Số_tiền]`")

    elif text == "🚀 Dua top":
        await update.message.reply_text("🚀 **BẢNG XẾP HẠNG ĐUA TOP**\n1. Chưa có dữ liệu tuần này.")

    elif text == "🎁 Event":
        await update.message.reply_text("🎁 Nhận code miễn phí mỗi ngày tại kênh thông báo sự kiện.")

    elif text == "🔍 Lệnh":
        # Đã lược bỏ hoàn toàn các lệnh Admin ra khỏi giao diện hiển thị cho người chơi thường
        help_text = (
            "📜 **DANH SÁCH LỆNH**\n\n"
            "🎲 **Game Tài Xỉu:**\n"
            "• `T/X/C/L [tiền]` (VD: `T 10k`, `T all`) — Cược Tài/Xỉu/Chẵn/Lẻ (Max 3M/bên)\n"
            "• `/lamcai [số tiền]` — Làm cái (1M - 5M)\n"
            "• `/nhanthuong` — Nhận thưởng sự kiện (Cần cược tối thiểu 20k trong phiên)\n"
            "• `/muagift [số_lượng] [mệnh_giá]` — Mua giftcode tự động từ số dư (VD: `/muagift 1 10000`)\n"
            "• `/sd` hoặc `/sodu` — Kiểm tra số dư\n\n"
            "💰 **TÀI KHOẢN:**\n"
            "• `/nap [tiền]` — Nạp tiền\n"
            "• `/rut [tiền]` hoặc `/rut all` — Rút tiền (Min 100k - Max 10M)\n"
            "• `/lsnap`, `/lsrut`, `/lschoi` — Lịch sử\n"
            "• `/caidatbank [stk] [mã_bank] [tên]` — Cài STK\n"
            "• `/chuyen [uid] [tiền]` — Chuyển tiền nội bộ"
        )
        await update.message.reply_text(help_text, parse_mode="Markdown")

async def lamcai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    args = context.args
    if not args:
        await update.message.reply_text(
            "⚠️ Dùng: `/lamcai [số_tiền]`\n"
            "📌 Hạn mức: `1.000.000 - 5.000.000`",
            parse_mode="Markdown"
        )
        return
    try:
        tien_cai = int(args[0])
    except ValueError:
        return
    
    if tien_cai < 1000000 or tien_cai > 5000000:
        await update.message.reply_text("❌ Số tiền làm cái phải từ `1.000.000đ` đến `5.000.000đ`!", parse_mode="Markdown")
        return
    if user["balance"] < tien_cai:
        await update.message.reply_text("❌ Số dư tài khoản không đủ để làm cái!")
        return
    
    user["balance"] -= tien_cai
    save_data()
    await update.message.reply_text(f"✅ Đăng ký làm cái thành công với số tiền thế chấp `{tien_cai:,}đ`!", parse_mode="Markdown")

async def nhanthuong_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    user_id_str = str(user_id)
    
    user_bet_in_session = user_session_total_bet.get(user_id, 0)
    if user_bet_in_session < 20000:
        await update.message.reply_text(
            f"❌ Bạn chưa đủ điều kiện nhận thưởng!\n"
            f"📌 Yêu cầu: Cần cược tối thiểu `20,000đ` trong phiên này (Bạn đã cược: `{user_bet_in_session:,}đ`).",
            parse_mode="Markdown"
        )
        return

    if len(user_id_str) < 2:
        await update.message.reply_text("❌ Không đủ điều kiện nhận thưởng.")
        return
        
    last_two_digits = int(user_id_str[-2:])
    if last_two_digits == lucky_number:
        thuong = lucky_reward
        user["balance"] += thuong
        save_data()
        await update.message.reply_text(f"🎉 Chúc mừng! ID của bạn có 2 số cuối khớp với số may mắn `{lucky_number:02d}`. Bạn nhận được phần thưởng `+{thuong:,}đ`", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ 2 số cuối ID của bạn ({last_two_digits:02d}) không trùng với số may mắn ({lucky_number:02d}).")

async def caidatbank_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("⚠️ Dùng: `/caidatbank [stk] [ngân_hàng] [tên]`", parse_mode="Markdown")
        return
    user["bank_info"] = f"{args[0]} - {args[1].upper()} - {' '.join(args[2:]).upper()}"
    save_data()
    await update.message.reply_text(f"✅ Đã cài đặt STK thành công: `{user['bank_info']}`", parse_mode="Markdown")

async def rut_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    args = context.args
    if not user["bank_info"]:
        await update.message.reply_text("❌ Chưa cài STK! Dùng `/caidatbank` trước.")
        return
    if not args:
        await update.message.reply_text("⚠️ Dùng: `/rut [số_tiền]` hoặc `/rut all` (Min 100k - Max 10M)")
        return
    try:
        rut_tien = user["balance"] if args[0].lower() in ["all", "max"] else int(args[0])
    except ValueError:
        return
    
    if rut_tien < 100000:
        await update.message.reply_text("❌ Số tiền rút tối thiểu là `100.000 VNĐ`!", parse_mode="Markdown")
        return
    if rut_tien > 10000000:
        await update.message.reply_text("❌ Số tiền rút tối đa mỗi lần là `10.000.000 VNĐ`!", parse_mode="Markdown")
        return
    if rut_tien > user["balance"]:
        await update.message.reply_text("❌ Số dư tài khoản không đủ để rút số tiền này!")
        return

    if user["total_bet"] < user["required_turnover"]:
        con_thieu = user["required_turnover"] - user["total_bet"]
        await update.message.reply_text(
            f"❌ **CHƯA ĐỦ ĐIỀU KIỆN RÚT TIỀN!**\n"
            f"📊 Tổng cược hiện tại: `{user['total_bet']:,}đ`\n"
            f"🎯 Vòng cược yêu cầu: `{user['required_turnover']:,}đ`\n"
            f"⚠️ Bạn cần cược thêm ` {con_thieu:,}đ ` nữa mới được phép rút.",
            parse_mode="Markdown"
        )
        return

    user["balance"] -= rut_tien
    save_data()

    ma_rut = str(random.randint(100000, 999999))
    pending_rut[ma_rut] = {"user_id": user_id, "amount": rut_tien}
    
    if GROUP_CHAT_ID:
        try:
            await context.bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text=(
                    f"💳 **THÔNG BÁO TẠO LỆNH RÚT TIỀN**\n"
                    f"👤 Khách ID: `{user_id}`\n"
                    f"💸 Số tiền rút: `{rut_tien:,}đ`\n"
                    f"🏦 Ngân hàng: `{user['bank_info']}`\n"
                    f"📌 Mã GD: `#{ma_rut}`"
                ),
                parse_mode="Markdown"
            )
        except Exception:
            pass

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id, 
                text=(
                    f"🔔 **YÊU CẦU RÚT TIỀN**\n"
                    f"ID: `{user_id}`\n"
                    f"Số tiền: `{rut_tien:,}đ`\n"
                    f"🏦 STK: `{user['bank_info']}`\n"
                    f"Mã GD: `{ma_rut}`\n\n"
                    f"👉 Duyệt: `/duyetrut {ma_rut}`\n"
                    f"👉 Từ chối: `/tuchoirut {ma_rut}`"
                ), 
                parse_mode="Markdown"
            )
        except Exception:
            pass

    await update.message.reply_text(f"✅ Gửi yêu cầu rút `{rut_tien:,}đ` thành công! Mã GD: `#{ma_rut}`. Vui lòng đợi Admin xử lý.")

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

        if GROUP_CHAT_ID:
            try:
                await context.bot.send_message(
                    chat_id=GROUP_CHAT_ID,
                    text=(
                        f"🟩 **THÔNG BÁO TẠO LỆNH NẠP TIỀN**\n"
                        f"👤 Khách ID: `{user_id}`\n"
                        f"💵 Số tiền nạp: `{amount:,}đ`\n"
                        f"📌 Mã GD: `#{magd}`"
                    ),
                    parse_mode="Markdown"
                )
            except Exception:
                pass

        noi_dung_ck = f"NAP{user_id}{magd}"
        caption_text = (
            f"🟩 **THÔNG TIN NẠP TIỀN**\n\n"
            f"🆔 ID: `{user_id}`\n"
            f"🪙 Ví TK: `{get_user(user_id)['balance']:,}`\n\n"
            f"Số tiền nạp: **{amount:,} VNĐ**\n"
            f"Tiền thưởng: **+0**\n"
            f"Dự kiến nhận được: **{amount:,} VNĐ**\n"
            f"Cách nạp: **BANK**\n"
            f"Ngân hàng nhận: **TPBANK**\n"
            f"Tên chủ tài khoản: **LUC TUAN HUNG**\n"
            f"Số tài khoản: **10006353242**\n"
            f"Nội dung chuyển khoản:\n`{noi_dung_ck}`\n\n"
            f"Mã đơn: `DP{random.randint(10000000000000, 99999999999999)}`\n"
            f"Đơn sẽ hết hạn sau **10 phút**, vui lòng thanh toán trong thời gian này."
        )
        await query.message.reply_text(caption_text, parse_mode="Markdown")

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
        save_data()
        await query.message.reply_text(f"🎁 Nhận hoàn cược: `+{t:,}đ`", parse_mode="Markdown")
    elif data == "ho_tro":
        await query.message.reply_text("🎧 Hỗ trợ 24/7.")
    elif data == "nap_nganhang":
        magd = random.randint(100000, 999999)
        pending_nap[str(magd)] = {"user_id": user_id, "amount": 50000}
        
        if GROUP_CHAT_ID:
            try:
                await context.bot.send_message(
                    chat_id=GROUP_CHAT_ID,
                    text=(
                        f"🟩 **THÔNG BÁO TẠO LỆNH NẠP TIỀN**\n"
                        f"👤 Khách ID: `{user_id}`\n"
                        f"💵 Số tiền nạp: `50,000đ`\n"
                        f"📌 Mã GD: `#{magd}`"
                    ),
                    parse_mode="Markdown"
                )
            except Exception:
                pass

        noi_dung_ck = f"NAP{user_id}{magd}"
        caption_text = (
            f"🟩 **THÔNG TIN NẠP TIỀN**\n\n"
            f"🆔 ID: `{user_id}`\n"
            f"🪙 Ví TK: `{get_user(user_id)['balance']:,}`\n\n"
            f"Số tiền nạp: **50,000 VNĐ**\n"
            f"Tiền thưởng: **+0**\n"
            f"Dự kiến nhận được: **50,000 VNĐ**\n"
            f"Cách nạp: **BANK**\n"
            f"Ngân hàng nhận: **TPBANK**\n"
            f"Tên chủ tài khoản: **LUC TUAN HUNG**\n"
            f"Số tài khoản: **10006353242**\n"
            f"Nội dung chuyển khoản:\n`{noi_dung_ck}`\n\n"
            f"Mã đơn: `DP{random.randint(10000000000000, 99999999999999)}`\n"
            f"Đơn sẽ hết hạn sau **10 phút**, vui lòng thanh toán trong thời gian này."
        )
        await query.message.reply_text(caption_text, parse_mode="Markdown")

async def run_taixiu_loop(application):
    global current_session, session_bets, user_session_bets, user_session_total_bet, huvang_pool, forced_dice_result, history_sessions, is_betting_open, lucky_number, lucky_reward
    
    while True:
        try:
            session_bets = {"T": 0, "X": 0, "C": 0, "L": 0}
            user_session_bets = {}
            user_session_total_bet = {}  
            is_betting_open = True  
            
            lucky_number = random.randint(0, 99)
            lucky_reward = random.randint(5, 50) * 1000
            
            target_chat = GROUP_CHAT_ID if GROUP_CHAT_ID else None
            
            # MỞ PHIÊN: MỞ KHÓA CHAT CHO THÀNH VIÊN TRONG NHÓM
            if target_chat:
                try:
                    await application.bot.set_chat_permissions(
                        chat_id=target_chat,
                        permissions=ChatPermissions(
                            can_send_messages=True,
                            can_send_media_messages=True,
                            can_send_polls=True,
                            can_send_other_messages=True,
                            can_add_web_page_previews=True
                        )
                    )
                except Exception as e:
                    logging.error(f"Lỗi mở quyền chat nhóm: {e}")

            start_text = (
                f"🐸 TuanHung88 - TUNG XX 🎲\n"
                f"🔥 **Xin mời đặt cược phiên XX**\n"
                f"**#{current_session}** 🔥\n\n"
                f"💲 **Min: 100 | Max mỗi bên: 3.000.000**\n\n"
                f"🎯 **Cách chơi: Cửa cược số tiền** (VD: `T 10k`, `T all`)\n"
                f"🔵 Tài: T | 🔴 Xỉu: X | ⚪ Chẵn: C | ⚫ Lẻ: L"
            )
            keyboard_start = [[InlineKeyboardButton("🐸 Vào bot chơi", url="https://t.me/tuanhung88_bot")]]
            
            if target_chat:
                try:
                    await application.bot.send_message(chat_id=target_chat, text=start_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard_start))
                except Exception as e:
                    logging.error(f"Lỗi gửi tin nhắn mở phiên: {e}")
            
            await asyncio.sleep(20)
            if target_chat:
                try:
                    await application.bot.send_message(
                        chat_id=target_chat, 
                        text=(
                            f"🦸‍♂️ **Còn 40 giây phiên #{current_session}**\n"
                            f"🔵 **TÀI: {session_bets['T']:,}**\n"
                            f"🔴 **XỈU: {session_bets['X']:,}**\n\n"
                            f"⚪ **CHẴN: {session_bets['C']:,}**\n"
                            f"⚫ **LẺ: {session_bets['L']:,}**"
                        ), 
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass
            await asyncio.sleep(20)
            if target_chat:
                try:
                    await application.bot.send_message(
                        chat_id=target_chat, 
                        text=(
                            f"🦸‍♂️ **Còn 20 giây phiên #{current_session}**\n"
                            f"🔵 **TÀI: {session_bets['T']:,}**\n"
                            f"🔴 **XỈU: {session_bets['X']:,}**\n\n"
                            f"⚪ **CHẴN: {session_bets['C']:,}**\n"
                            f"⚫ **LẺ: {session_bets['L']:,}**"
                        ), 
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass
            await asyncio.sleep(10)
            if target_chat:
                try:
                    await application.bot.send_message(
                        chat_id=target_chat, 
                        text=(
                            f"🦸‍♂️ **Còn 10 giây phiên #{current_session}**\n"
                            f"🔵 **TÀI: {session_bets['T']:,}**\n"
                            f"🔴 **XỈU: {session_bets['X']:,}**\n\n"
                            f"⚪ **CHẴN: {session_bets['C']:,}**\n"
                            f"⚫ **LẺ: {session_bets['L']:,}**"
                        ), 
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass
            await asyncio.sleep(10)
            
            is_betting_open = False  

            # HẾT GIỜ CƯỢC: KHÓA CHAT NHÓM (CẤM NHẮN TIN)
            if target_chat:
                try:
                    await application.bot.set_chat_permissions(
                        chat_id=target_chat,
                        permissions=ChatPermissions(
                            can_send_messages=False,
                            can_send_media_messages=False,
                            can_send_polls=False,
                            can_send_other_messages=False,
                            can_add_web_page_previews=False
                        )
                    )
                except Exception as e:
                    logging.error(f"Lỗi khóa quyền chat nhóm: {e}")

            if target_chat:
                try:
                    end_bet_text = (
                        f"🦸‍♂️ **Hết thời gian đặt cược phiên**\n"
                        f"**#{current_session}**\n"
                        f"🔵 **TÀI: {session_bets['T']:,}**\n"
                        f"🔴 **XỈU: {session_bets['X']:,}**\n\n"
                        f"⚪ **CHẴN: {session_bets['C']:,}**\n"
                        f"⚫ **LẺ: {session_bets['L']:,}**"
                    )
                    await application.bot.send_message(chat_id=target_chat, text=end_bet_text, parse_mode="Markdown")
                    await application.bot.send_message(chat_id=target_chat, text=f"💥 **Bắt đầu tung XX phiên**\n**#{current_session}**", parse_mode="Markdown")
                except Exception:
                    pass
            
            dice_values = []
            current_forced = forced_dice_result  
            forced_dice_result = None  

            # SỬA LỖI CHỈNH XÚC XẮC: Ép kết quả chuẩn xác 100%
            if current_forced == "TAI":
                while True:
                    d1, d2, d3 = random.randint(1, 6), random.randint(1, 6), random.randint(1, 6)
                    if (d1 + d2 + d3) >= 11:
                        dice_values = [d1, d2, d3]
                        break
            elif current_forced == "XIU":
                while True:
                    d1, d2, d3 = random.randint(1, 6), random.randint(1, 6), random.randint(1, 6)
                    if (d1 + d2 + d3) <= 10:
                        dice_values = [d1, d2, d3]
                        break
            else:
                if target_chat:
                    for _ in range(3):
                        try:
                            msg_d = await application.bot.send_dice(chat_id=target_chat, emoji="🎲")
                            val = getattr(msg_d.dice, 'value', None)
                            if val is None:
                                val = random.randint(1, 6)
                            dice_values.append(val)
                            await asyncio.sleep(0.8)
                        except Exception as e:
                            logging.error(f"Lỗi khi tung xúc xắc: {e}")
                            dice_values.append(random.randint(1, 6))
                else:
                    dice_values = [random.randint(1, 6), random.randint(1, 6), random.randint(1, 6)]

            while len(dice_values) < 3:
                dice_values.append(random.randint(1, 6))

            tong = sum(dice_values)
            ket_qua_tx = "TÀI" if tong >= 11 else "XỈU"
            ket_qua_cl = "CHẴN" if tong % 2 == 0 else "LẺ"
            
            icon_tx = "🔵" if ket_qua_tx == "TÀI" else "🔴"
            icon_cl = "⚪" if ket_qua_cl == "CHẴN" else "⚫"
            
            history_sessions.append((icon_tx, icon_cl))
            if len(history_sessions) > 12:
                history_sessions.pop(0)
                
            row_tx = "".join([tx for tx, cl in history_sessions])
            row_cl = "".join([cl for tx, cl in history_sessions])
            
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
                        u["history_choi"].append(f"Phiên #{current_session}: Cược TÀI {bets['T']:,}đ -> Thắng +{thuong:,}đ")
                        try:
                            await application.bot.send_message(chat_id=u_id, text=f"✅ **Thắng phiên #{current_session}**\nCược TÀI - {bets['T']:,}\nTiền nhận: {thuong:,}\nSố dư mới: {u['balance']:,}", parse_mode="Markdown")
                        except Exception:
                            pass
                    else:
                        thua_user += bets["T"]
                        u["history_choi"].append(f"Phiên #{current_session}: Cược TÀI {bets['T']:,}đ -> Thua -{bets['T']:,}đ")
                        try:
                            await application.bot.send_message(chat_id=u_id, text=f"❌ **Thua phiên #{current_session}**\nCược TÀI - {bets['T']:,}\nTiền nhận: 0\nSố dư mới: {u['balance']:,}", parse_mode="Markdown")
                        except Exception:
                            pass

                if bets["X"] > 0:
                    if ket_qua_tx == "XỈU":
                        thuong = int(bets["X"] * 1.95)
                        thang_user += thuong
                        u["balance"] += thuong
                        u["history_choi"].append(f"Phiên #{current_session}: Cược XỈU {bets['X']:,}đ -> Thắng +{thuong:,}đ")
                        try:
                            await application.bot.send_message(chat_id=u_id, text=f"✅ **Thắng phiên #{current_session}**\nCược XỈU - {bets['X']:,}\nTiền nhận: {thuong:,}\nSố dư mới: {u['balance']:,}", parse_mode="Markdown")
                        except Exception:
                            pass
                    else:
                        thua_user += bets["X"]
                        u["history_choi"].append(f"Phiên #{current_session}: Cược XỈU {bets['X']:,}đ -> Thua -{bets['X']:,}đ")
                        try:
                            await application.bot.send_message(chat_id=u_id, text=f"❌ **Thua phiên #{current_session}**\nCược XỈU - {bets['X']:,}\nTiền nhận: 0\nSố dư mới: {u['balance']:,}", parse_mode="Markdown")
                        except Exception:
                            pass

                if bets["C"] > 0:
                    if ket_qua_cl == "CHẴN":
                        thuong = int(bets["C"] * 1.95)
                        thang_user += thuong
                        u["balance"] += thuong
                        u["history_choi"].append(f"Phiên #{current_session}: Cược CHẴN {bets['C']:,}đ -> Thắng +{thuong:,}đ")
                        try:
                            await application.bot.send_message(chat_id=u_id, text=f"✅ **Thắng phiên #{current_session}**\nCược CHẴN - {bets['C']:,}\nTiền nhận: {thuong:,}\nSố dư mới: {u['balance']:,}", parse_mode="Markdown")
                        except Exception:
                            pass
                    else:
                        thua_user += bets["C"]
                        u["history_choi"].append(f"Phiên #{current_session}: Cược CHẴN {bets['C']:,}đ -> Thua -{bets['C']:,}đ")
                        try:
                            await application.bot.send_message(chat_id=u_id, text=f"❌ **Thua phiên #{current_session}**\nCược CHẴN - {bets['C']:,}\nTiền nhận: 0\nSố dư mới: {u['balance']:,}", parse_mode="Markdown")
                        except Exception:
                            pass

                if bets["L"] > 0:
                    if ket_qua_cl == "LẺ":
                        thuong = int(bets["L"] * 1.95)
                        thang_user += thuong
                        u["balance"] += thuong
                        u["history_choi"].append(f"Phiên #{current_session}: Cược LẺ {bets['L']:,}đ -> Thắng +{thuong:,}đ")
                        try:
                            await application.bot.send_message(chat_id=u_id, text=f"✅ **Thắng phiên #{current_session}**\nCược LẺ - {bets['L']:,}\nTiền nhận: {thuong:,}\nSố dư mới: {u['balance']:,}", parse_mode="Markdown")
                        except Exception:
                            pass
                    else:
                        thua_user += bets["L"]
                        u["history_choi"].append(f"Phiên #{current_session}: Cược LẺ {bets['L']:,}đ -> Thua -{bets['L']:,}đ")
                        try:
                            await application.bot.send_message(chat_id=u_id, text=f"❌ **Thua phiên #{current_session}**\nCược LẺ - {bets['L']:,}\nTiền nhận: 0\nSố dư mới: {u['balance']:,}", parse_mode="Markdown")
                        except Exception:
                            pass
                    
                tong_thang += thang_user
                tong_thua += thua_user

            save_data() 
            huvang_pool += random.randint(100, 500)
            
            ket_qua_msg = (
                f"| **{dice_values[0]} {dice_values[1]} {dice_values[2]}** {icon_tx} **{ket_qua_tx} {ket_qua_cl}** {icon_tx} {icon_cl}\n"
                f"| {icon_tx} **Tổng điểm xúc xắc: {tong}**\n"
                f"| (3-18)\n"
                f"|\n"
                f"| ｜ **Tổng thắng: {tong_thang:,}**\n"
                f"| ｜ **Tổng thua: {tong_thua:,}**\n"
                f"| ｜ **Công hũ: +{random.randint(50, 999)}**\n"
                f"| ｜ **Hũ hiện tại: {huvang_pool:,}**\n"
                f"└─────────────────────────\n\n"
                f"💬 **Thống kê {len(history_sessions)} phiên gần nhất:**\n"
                f"{row_tx}\n"
                f"{row_cl}"
            )
            
            if target_chat:
                try:
                    keyboard_kq = [
                        [InlineKeyboardButton("💲 Nạp tiền", url="https://t.me/tuanhung88_bot"), InlineKeyboardButton("📜 Lịch sử phiên", url="https://t.me/tuanhung88_bot")]
                    ]
                    await application.bot.send_message(
                        chat_id=target_chat,
                        text=f"🎉 **Kết quả XX phiên #{current_session}**\n\n{ket_qua_msg}",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup(keyboard_kq)
                    )
                    
                    await application.bot.send_message(
                        chat_id=target_chat,
                        text=(
                            f"🍀 **Con số may mắn của phiên này: {lucky_number:02d}**\n"
                            f"🎁 **Tiền thưởng ngẫu nhiên: {lucky_reward:,}đ**\n"
                            f"⚠️ **Điều kiện:** Phải cược tối thiểu `20,000đ` trong phiên này mới được nhận thưởng.\n"
                            f"Nếu 2 số cuối ID của bạn trùng số may mắn, hãy chat lệnh `/nhanthuong` để nhận."
                        ),
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass
            
            current_session += 1
            await asyncio.sleep(3)
        except Exception as loop_err:
            logging.error(f"Lỗi bên trong vòng lặp Tài Xỉu (đã tự động phục hồi): {loop_err}")
            await asyncio.sleep(5)

# --- QUẢN TRỊ ADMIN ---
async def check_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Dùng: `/check [ID_user]`", parse_mode="Markdown")
        return
    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ ID không hợp lệ!")
        return

    if target_id not in users_db:
        await update.message.reply_text(f"❌ Không tìm thấy thông tin của user ID `{target_id}`.", parse_mode="Markdown")
        return

    u = users_db[target_id]
    update_vip(u)
    
    ls_choi_gần_nhất = "\n".join(u["history_choi"][-5:]) if u["history_choi"] else "Chưa có lịch sử chơi"
    ls_nap_gần_nhất = "\n".join(u["history_nap"][-3:]) if u["history_nap"] else "Chưa có lịch sử nạp"
    ls_rut_gần_nhất = "\n".join(u["history_rut"][-3:]) if u["history_rut"] else "Chưa có lịch sử rút"

    info_str = (
        f"🔍 **THÔNG TIN KHÁCH CHƠI (ID: {target_id})**\n\n"
        f"🪙 Số dư: `{u['balance']:,} VNĐ`\n"
        f"📊 Tổng cược tích lũy: `{u['total_bet']:,} VNĐ`\n"
        f"🎯 Vòng cược yêu cầu: `{u['required_turnover']:,} VNĐ`\n"
        f"👑 Cấp VIP: `{u['vip_level']}` (Điểm: {u['vip_points']})\n"
        f"🎁 Đã nhận X2 lần đầu: `{'Rồi ✅' if u.get('has_received_x2') else 'Chưa ❌'}`\n"
        f"🏦 Ngân hàng: `{u['bank_info'] if u['bank_info'] else 'Chưa cài'}`\n"
        f"🔰 Trạng thái: `{'Tân thủ' if u['is_newbie'] else 'Chính thức'}`\n\n"
        f"📜 **5 Lịch sử chơi gần nhất:**\n{ls_choi_gần_nhất}\n\n"
        f"🟩 **Lịch sử nạp:**\n{ls_nap_gần_nhất}\n\n"
        f"🟥 **Lịch sử rút:**\n{ls_rut_gần_nhất}"
    )
    await update.message.reply_text(info_str, parse_mode="Markdown")

async def mo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Dùng: `/mo [ID_user]` để mở khóa tân thủ cho người chơi.", parse_mode="Markdown")
        return
    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ ID không hợp lệ!")
        return

    if target_id not in users_db:
        await update.message.reply_text(f"❌ Không tìm thấy user ID `{target_id}` trong hệ thống.", parse_mode="Markdown")
        return

    users_db[target_id]["is_newbie"] = False
    save_data()

    await update.message.reply_text(f"✅ Đã mở khóa thành công! User ID `{target_id}` không còn là tân thủ (Đã bỏ giới hạn cược max 10k).", parse_mode="Markdown")
    try:
        await context.bot.send_message(chat_id=target_id, text="🎉 Tài khoản của bạn đã được Admin mở khóa! Bạn có thể đặt cược hạn mức cao hơn.", parse_mode="Markdown")
    except Exception:
        pass

async def congvongcuoc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("⚠️ Dùng: `/congvongcuoc [ID_user] [số_vòng_cần_cộng]`", parse_mode="Markdown")
        return
    try:
        target_id = int(args[0])
        vong_them = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ ID hoặc số vòng cược phải là số nguyên!")
        return

    u = get_user(target_id)
    u["required_turnover"] += vong_them
    save_data()

    await update.message.reply_text(f"✅ Đã cộng thêm vòng cược cho user `{target_id}` thành công!\n📊 Tổng yêu cầu cược hiện tại: `{u['required_turnover']:,}đ`", parse_mode="Markdown")

async def duyet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    args = context.args
    if not args:
        return
    ma_gd = args[0]
    if ma_gd in pending_nap:
        info = pending_nap[ma_gd]
        user_id = info["user_id"]
        u = get_user(user_id)
        u["is_newbie"] = False
        
        so_tien_nap = info["amount"]
        thuc_nhan = so_tien_nap
        x2_msg = ""
        
        if not u.get("has_received_x2", False):
            thuc_nhan = so_tien_nap * 2
            u["has_received_x2"] = True
            vong_cuoc = (so_tien_nap * 2) * 4  
            u["required_turnover"] += vong_cuoc
            x2_msg = f"\n🎁 **Khuyến mãi X2:** Nhận `{thuc_nhan:,}đ` | Yêu cầu cược x4 (`{vong_cuoc:,}đ`) để rút!"
        else:
            vong_cuoc = so_tien_nap * 2  
            u["required_turnover"] += vong_cuoc
            x2_msg = f"\n📌 **Nạp từ lần 2:** Yêu cầu cược x2 (`{vong_cuoc:,}đ`) để rút!"

        u["balance"] += thuc_nhan
        u["history_nap"].append(f"Nạp thành công {so_tien_nap:,}đ (Thực nhận {thuc_nhan:,}đ)")
        save_data()
        del pending_nap[ma_gd]
        
        if GROUP_CHAT_ID:
            try:
                await context.bot.send_message(
                    chat_id=GROUP_CHAT_ID,
                    text=(
                        f"✅ **THÔNG BÁO NẠP TIỀN THÀNH CÔNG**\n"
                        f"👤 Khách ID: `{user_id}`\n"
                        f"💵 Số tiền nạp: `{so_tien_nap:,}đ`\n"
                        f"💰 Thực nhận: `{thuc_nhan:,}đ`"
                    ),
                    parse_mode="Markdown"
                )
            except Exception:
                pass

        try:
            await context.bot.send_message(
                chat_id=user_id, 
                text=f"✅ **NẠP THÀNH CÔNG!**\nCộng `+{thuc_nhan:,}đ`{x2_msg}\n🪙 Số dư mới: `{u['balance']:,}đ`", 
                parse_mode="Markdown"
            )
        except Exception:
            pass
        await update.message.reply_text(f"✅ Đã duyệt mã nạp #{ma_gd} thành công (Thực nhận: {thuc_nhan:,}đ)!")

async def tuchoi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    args = context.args
    if not args:
        return
    ma_gd = args[0]
    if ma_gd in pending_nap:
        del pending_nap[ma_gd]
        await update.message.reply_text(f"❌ Đã từ chối mã nạp #{ma_gd}.")

async def duyetrut_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Dùng: `/duyetrut [mã_gd]`")
        return
    ma_rut = args[0]
    if ma_rut in pending_rut:
        info = pending_rut[ma_rut]
        u = get_user(info["user_id"])
        u["history_rut"].append(f"Rút thành công {info['amount']:,}đ về {u['bank_info']}")
        save_data()
        del pending_rut[ma_rut]
        try:
            await context.bot.send_message(
                chat_id=info["user_id"], 
                text=f"✅ **RÚT TIỀN THÀNH CÔNG!**\nAdmin đã chuyển khoản `{info['amount']:,}đ` về STK của bạn.", 
                parse_mode="Markdown"
            )
        except Exception:
            pass
        await update.message.reply_text(f"✅ Đã duyệt lệnh rút #{ma_rut} thành công!")
    else:
        await update.message.reply_text("❌ Không tìm thấy mã rút tiền này hoặc đã được xử lý!")

async def tuchoirut_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Dùng: `/tuchoirut [mã_gd]`")
        return
    ma_rut = args[0]
    if ma_rut in pending_rut:
        info = pending_rut[ma_rut]
        u = get_user(info["user_id"])
        u["balance"] += info["amount"]
        save_data()
        del pending_rut[ma_rut]
        try:
            await context.bot.send_message(
                chat_id=info["user_id"], 
                text=f"❌ **YÊU CẦU RÚT TIỀN BỊ TỪ CHỐI!**\nSố tiền `{info['amount']:,}đ` đã được hoàn lại vào số dư của bạn.", 
                parse_mode="Markdown"
            )
        except Exception:
            pass
        await update.message.reply_text(f"❌ Đã từ chối lệnh rút #{ma_rut} và hoàn tiền cho người chơi.")
    else:
        await update.message.reply_text("❌ Không tìm thấy mã rút tiền này hoặc đã được xử lý!")

async def thutien_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "⚠️ **Cú pháp thu/trừ tiền thủ công:**\n"
            "• Cộng tiền: `/thutien [ID_user] +[số_tiền]`\n"
            "• Trừ tiền: `/thutien [ID_user] -[số_tiền]`\n"
            "VD: `/thutien 8361791292 +50k`",
            parse_mode="Markdown"
        )
        return
    
    try:
        target_user_id = int(args[0])
        amount_str = args[1].lower()
        is_minus = amount_str.startswith("-")
        if is_minus or amount_str.startswith("+"):
            amount_str = amount_str[1:]
            
        cleaned = amount_str.replace(",", "").replace(".", "")
        if cleaned.endswith("k"):
            amount = int(cleaned[:-1]) * 1000
        elif cleaned.endswith("m"):
            amount = int(cleaned[:-1]) * 1000000
        else:
            amount = int(cleaned)
            
        if is_minus:
            amount = -amount

    except ValueError:
        await update.message.reply_text("❌ Sai định dạng số tiền! (VD: `50k`, `100000`, `-50000`)")
        return

    target_user = get_user(target_user_id)
    target_user["balance"] += amount
    
    if amount > 0:
        target_user["is_newbie"] = False
        target_user["history_nap"].append(f"Admin cộng thủ công: +{amount:,}đ")
        
    save_data()

    await update.message.reply_text(
        f"✅ **ĐÃ THỰC THI THÀNH CÔNG!**\n"
        f"👤 ID: `{target_user_id}`\n"
        f"💸 Biến động: `{amount:+,}đ`\n"
        f"🪙 Số dư mới: `{target_user['balance']:,}đ`",
        parse_mode="Markdown"
    )

    try:
        action_text = f"nhận được `+{amount:,}đ`" if amount > 0 else f"bị trừ `{amount:,}đ`"
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"🔔 **THÔNG BÁO TỪ HỆ THỐNG**\nTài khoản của bạn vừa {action_text} từ Admin.\n🪙 Số dư hiện tại: `{target_user['balance']:,}đ`",
            parse_mode="Markdown"
        )
    except Exception:
        pass

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
        save_data()
        del giftcode_db[code]
        
        if GROUP_CHAT_ID:
            try:
                await context.bot.send_message(
                    chat_id=GROUP_CHAT_ID,
                    text=(
                        f"🎁 **THÔNG BÁO NHẬP GIFTCODE**\n"
                        f"👤 Khách ID: `{user_id}`\n"
                        f"🎫 Mã code: `{code}`\n"
                        f"💰 Giá trị nhận: `{val:,}đ`"
                    ),
                    parse_mode="Markdown"
                )
            except Exception:
                pass

        await update.message.reply_text(f"🎉 **NHẬP CODE THÀNH CÔNG!**\n🎁 Nhận: `+{val:,} VNĐ`", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Mã code không tồn tại hoặc đã được sử dụng!")

async def muagift_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    user_id = update.effective_user.id
    user = get_user(user_id)
    if len(args) < 2:
        await update.message.reply_text("⚠️ Dùng: `/muagift [số_lượng] [mệnh_giá]` (VD: `/muagift 1 10000`)", parse_mode="Markdown")
        return
    try:
        soluong, menh_gia = int(args[0]), int(args[1])
    except ValueError:
        await update.message.reply_text("❌ Sai định dạng số lượng hoặc mệnh giá!")
        return

    available_codes = [code for code, val in giftcode_db.items() if val == menh_gia]
    if len(available_codes) < soluong:
        await update.message.reply_text(f"❌ Kho hiện chỉ còn {len(available_codes)} mã mệnh giá {menh_gia:,}đ.")
        return

    tong_thanh_toan = int((soluong * menh_gia) * 1.05) 
    if user["balance"] < tong_thanh_toan:
        await update.message.reply_text(f"❌ Số dư không đủ! Cần `{tong_thanh_toan:,}đ` (gồm 5% phí giao dịch).")
        return

    user["balance"] -= tong_thanh_toan
    save_data()

    bought_codes = []
    for _ in range(soluong):
        c = available_codes.pop(0)
        del giftcode_db[c]
        bought_codes.append(c)

    await update.message.reply_text(
        f"✅ **MUA GIFTCODE THÀNH CÔNG!**\n"
        f"🎫 Mệnh giá: `{menh_gia:,}đ` x {soluong}\n"
        f"💸 Trừ số dư: `{tong_thanh_toan:,}đ` (đã gồm 5% phí)\n"
        f"🎁 Mã của bạn: `" + ", ".join(bought_codes) + "`",
        parse_mode="Markdown"
    )

async def chinhxucxac_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global forced_dice_result
    if update.effective_user.id not in ADMIN_IDS:
        return
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Dùng: `/chinhxucxac tai` hoặc `/chinhxucxac xiu` hoặc `/chinhxucxac reset`")
        return
    mode = args[0].lower()
    if mode in ["tai", "eptai"]:
        forced_dice_result = "TAI"
        await update.message.reply_text("⚡ Đã khóa 100% ra TÀI ngay phiên hiện tại!")
    elif mode in ["xiu", "epxiu"]:
        forced_dice_result = "XIU"
        await update.message.reply_text("⚡ Đã khóa 100% ra XỈU ngay phiên hiện tại!")
    else:
        forced_dice_result = None
        await update.message.reply_text("🔄 Đã reset xúc xắc ngẫu nhiên.")

TOKEN = "9286450426:AAHYoubtmQirYbLnmmN309OeA81sABUrxsA"

async def main():
    global is_loop_running
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("sd", sodu_command))
    application.add_handler(CommandHandler("sodu", sodu_command))
    application.add_handler(CommandHandler("caidatbank", caidatbank_command))
    application.add_handler(CommandHandler("rut", rut_command))
    application.add_handler(CommandHandler("check", check_user_command))
    application.add_handler(CommandHandler("mo", mo_command))
    application.add_handler(CommandHandler("congvongcuoc", congvongcuoc_command))
    application.add_handler(CommandHandler("duyet", duyet_command))
    application.add_handler(CommandHandler("tuchoi", tuchoi_command))
    application.add_handler(CommandHandler("duyetrut", duyetrut_command))
    application.add_handler(CommandHandler("tuchoirut", tuchoirut_command))
    application.add_handler(CommandHandler("thutien", thutien_command))
    application.add_handler(CommandHandler("trutien", thutien_command))
    application.add_handler(CommandHandler("lamcai", lamcai_command))
    application.add_handler(CommandHandler("nhanthuong", nhanthuong_command))
    application.add_handler(CommandHandler("muagift", muagift_command))
    application.add_handler(CommandHandler("taocode", taocode_command))
    application.add_handler(CommandHandler("themcode", themcode_command))
    application.add_handler(CommandHandler("xoacode", xoacode_command))
    application.add_handler(CommandHandler("danhsachcode", danhsachcode_command))
    application.add_handler(CommandHandler("code", code_command))
    application.add_handler(CommandHandler("nhapcode", code_command))
    application.add_handler(CommandHandler("chinhxucxac", chinhxucxac_command))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    await application.initialize()
    await application.start()
    
    if not is_loop_running:
        is_loop_running = True
        asyncio.create_task(run_taixiu_loop(application))
    
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    
    stop_signal = asyncio.get_running_loop().create_future()
    await stop_signal

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
