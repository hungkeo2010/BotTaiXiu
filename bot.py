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

# ID Admin chính thức
ADMIN_IDS = [8682451039]

# Biến toàn cục quản lý phiên Tài Xỉu và can thiệp xúc xắc 100% chính xác
forced_dice_result = None
current_session = 197892
session_bets = {"T": 0, "X": 0, "C": 0, "L": 0}
user_session_bets = {}  # {user_id: {"T": x, "X": y, ...}}

def get_user(user_id):
    if user_id not in users_db:
        users_db[user_id] = {
            "balance": 0,
            "total_bet": 0,
            "vip_points": 0,
            "vip_level": "Đồng 🥉",
            "is_newbie": True,  # Mặc định tài khoản mới là Tân thủ (Max cược 10k, cần nạp 50k mở khóa)
            "bank_info": None,  # Lưu thông tin ngân hàng cài đặt qua /caidatbank
            "history_nap": [],
            "history_rut": [],
            "history_choi": []
        }
    return users_db[user_id]

def update_vip(user_data):
    total = user_data["total_bet"]
    points = total // 100000  # 100k tổng cược = 1 điểm VIP
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

# --- BÀN PHÍM CHÍNH (REPLY KEYBOARD) ---
def get_main_menu():
    keyboard = [
        ["📁 Danh sách game", "📄 Tài khoản"],
        ["💲 Nạp Tiền", "💳 Rút Tiền"],
        ["🌸 Chuyển Tiền", "🚀 Dua top"],
        ["🎁 Event", "🔍 Lệnh"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- LỆNH /START ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    get_user(user_id)
    text = (
        f"🔵 **ID của bạn là `{user_id}`**\n\n"
        f"🏛️ Tham gia Room TX để săn hũ và nhận giftcode hằng ngày https://t.me/tuanhung88chat\n\n"
        f"💙 Tham gia kênh thông báo để nhận code hàng ngày 💙"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=get_main_menu())

# --- XỬ LÝ NHẮN TIN & ĐẶT CƯỢC TRÒ CHƠI ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
        
    text = update.message.text.strip()
    user_id = update.effective_user.id
    user = get_user(user_id)

    # Xử lý cược qua tin nhắn chat (Ví dụ: T 20000, X max, C 50000, L max)
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
                return  # Không phải cú pháp cược hợp lệ thì bỏ qua

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

        # Trừ tiền và ghi nhận cược phiên
        user["balance"] -= bet_amount
        user["total_bet"] += bet_amount
        
        session_bets[choice] += bet_amount
        if user_id not in user_session_bets:
            user_session_bets[user_id] = {"T": 0, "X": 0, "C": 0, "L": 0}
        user_session_bets[user_id][choice] += bet_amount

        full_name_choice = {"T": "TÀI", "X": "XỈU", "C": "CHẮN", "L": "LẺ"}[choice]
        await update.message.reply_text(
            f"✅ **Đặt thành công phiên #{current_session}**\n"
            f"| **{full_name_choice}**: `{bet_amount:,}đ`",
            parse_mode="Markdown"
        )
        return

    # Xử lý các nút Menu chính
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
            "✅ Mỗi lần nạp cần lấy thông tin **MỚI**.\n"
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
                "Để đổi STK vui lòng liên hệ Admin.\n\n"
                "💸 Rút tiền về tài khoản trên:\n"
                "• `/rut [số tiền]` - VD: `/rut 50000`\n"
                "• `/rut all` - Rút tối đa phần khả dụng (đã trừ phí 1%)\n\n"
                "📋 **Điều kiện rút tiền:**\n"
                "• Cược đủ mốc tiền nạp + số dư tân thủ giữ lại x3.\n"
                "• Số tiền đã nạp: `0đ`\n"
                "• Mốc cược cần đủ: `0đ`\n"
                "• Hiện đã cược: `0đ`\n\n"
                "❌ Chưa đủ điều kiện! Vui lòng cược thêm.\n\n"
                "⚠️ Phí rút 1%. Rút tối thiểu theo cài đặt bot (thường 50k)."
            )
            await update.message.reply_text(rut_text, parse_mode="Markdown")

    elif text == "🌸 Chuyển Tiền":
        await update.message.reply_text("🌸 Cú pháp chuyển tiền: `/chuyentien [ID_nhận] [Số_tiền]`")

    elif text == "🚀 Dua top":
        await update.message.reply_text("🚀 **BẢNG XẾP HẠNG ĐUA TOP**\n1. Chưa có dữ liệu tuần này.")

    elif text == "🎁 Event":
        await update.message.reply_text("🎁 Nhận code miễn phí mỗi ngày tại kênh thông báo sự kiện.")

    elif text == "🔍 Lệnh":
        if user_id in ADMIN_IDS:
            help_text = (
                "🔍 **HỆ THỐNG LỆNH HỖ TRỢ (ADMIN)**\n\n"
                "👤 **Thành viên:**\n"
                "• `T/X/C/L [tiền]` - Tài/Xỉu/Chẵn/Lẻ\n"
                "• `/nap [tiền]` - Nạp tiền\n"
                "• `/rut [tiền]` hoặc `/rut all` - Rút tiền\n"
                "• `/lsnap`, `/lsrut`, `/lschoi` - Lịch sử\n"
                "• `/caidatbank [stk] [bank] [tên]` - Cài STK\n"
                "• `/chuyen [uid] [tiền]` - Chuyển tiền\n"
                "• `/code [mã]` hoặc `/nhapcode [mã]` - Nhập giftcode\n"
                "• `/muagift [số_lượng] [mệnh_giá]` - Mua giftcode\n"
                "• `/ref` - Thông tin giới thiệu\n"
                "• `/doidiemvip [số_điểm]` - Đổi điểm VIP\n\n"
                "👑 **Admin / Chủ Bot:**\n"
                "• `/taocode [số_lượng] [tiền]` - Tạo nhanh giftcode\n"
                "• `/themcode [mã] [tiền]` - Thêm mã tùy chỉnh\n"
                "• `/xoacode [mã]` - Xóa mã trong kho\n"
                "• `/danhsachcode` - Xem danh sách giftcode\n"
                "• `/chinhxucxac [tai/xiu/reset]` - Hack kết quả chuẩn 100%\n"
                "• `/duyệt [mã_nạp]` - Duyệt nạp tiền & mở khóa Tân thủ"
            )
        else:
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
                "• `/muagift [số_lượng] [mệnh_giá]` — Mua giftcode\n"
                "• `/ref` — Thông tin giới thiệu\n"
                "• `/doidiemvip [số_điểm]` — Đổi điểm VIP"
            )
        await update.message.reply_text(help_text, parse_mode="Markdown")

# --- LỆNH CÀI ĐẶT NGÂN HÀNG & RÚT TIỀN ---
async def caidatbank_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    args = context.args

    if len(args) < 3:
        await update.message.reply_text(
            "⚠️ Sai cú pháp! Vui lòng dùng:\n"
            "`/caidatbank [stk] [ngân_hàng] [tên_chủ_tài_khoản]`\n"
            "Ví dụ: `/caidatbank 9520252005 MB LUC THUY LINH`",
            parse_mode="Markdown"
        )
        return

    stk = args[0]
    ngan_hang = args[1].upper()
    ten_chu_tk = " ".join(args[2:]).upper()

    user["bank_info"] = f"{stk} - {ngan_hang} - {ten_chu_tk}"
    await update.message.reply_text(
        f"✅ **CÀI ĐẶT TÀI KHOẢN NGÂN HÀNG THÀNH CÔNG!**\n\n"
        f"🧾 STK của bạn: `{user['bank_info']}`\n\n"
        f"Bây giờ bạn có thể bấm nút **Rút Tiền** ở menu chính để thực hiện lệnh rút.",
        parse_mode="Markdown"
    )

async def rut_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    args = context.args

    if not user["bank_info"]:
        await update.message.reply_text(
            "❌ Bạn chưa cài đặt tài khoản ngân hàng!\n"
            "Vui lòng dùng lệnh: `/caidatbank [stk] [ngân_hàng] [tên]` trước khi rút tiền.",
            parse_mode="Markdown"
        )
        return

    if not args:
        await update.message.reply_text(
            "⚠️ Vui lòng nhập số tiền muốn rút hoặc rút tối đa:\n"
            "• `/rut 50000`\n"
            "• `/rut all`",
            parse_mode="Markdown"
        )
        return

    try:
        if args[0].lower() == "all":
            if user["balance"] < 50000:
                await update.message.reply_text("❌ Số dư tối thiểu để rút là `50,000 VNĐ`!", parse_mode="Markdown")
                return
            rut_tien = user["balance"]
        else:
            rut_tien = int(args[0])
            if rut_tien < 50000:
                await update.message.reply_text("❌ Số tiền rút tối thiểu là `50,000 VNĐ`!", parse_mode="Markdown")
                return
            if rut_tien > user["balance"]:
                await update.message.reply_text("❌ Số dư tài khoản không đủ để thực hiện lệnh rút này!", parse_mode="Markdown")
                return
    except ValueError:
        await update.message.reply_text("⚠️ Số tiền rút phải là số hợp lệ hoặc chữ `all`!", parse_mode="Markdown")
        return

    phi = int(rut_tien * 0.01) # Phí rút 1%
    thuc_nhan = rut_tien - phi
    user["balance"] -= rut_tien
    user["history_rut"].append(f"Rút {rut_tien:,}đ (Thực nhận: {thuc_nhan:,}đ, Phí: {phi:,}đ) về {user['bank_info']}")

    await update.message.reply_text(
        f"✅ **GỬI YÊU CẦU RÚT TIỀN THÀNH CÔNG!**\n\n"
        f"💸 Số tiền rút: `{rut_tien:,} VNĐ`\n"
        f"📉 Phí giao dịch (1%): `{phi:,} VNĐ`\n"
        f"💰 Thực nhận: `{thuc_nhan:,} VNĐ`\n"
        f"🏦 Tài khoản nhận: `{user['bank_info']}`\n\n"
        f"⏳ Giao dịch đang chờ Admin xử lý chuyển khoản tự động trong ít phút!",
        parse_mode="Markdown"
    )

# --- XỬ LÝ NÚT INLINE & GAME ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global forced_dice_result
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    data = query.data

    if data.startswith("nap_") and data != "nap_nganhang":
        amount_str = data.replace("nap_", "")
        amount = int(amount_str)
        magd = random.randint(100000, 999999)
        await query.message.reply_text(
            f"➕ **THÔNG TIN CHUYỂN KHOẢN NẠP {amount:,} VNĐ**\n\n"
            f"🏦 Ngân hàng: MBBANK\n"
            f"📌 STK: `0328122738`\n"
            f"💰 Chủ TK: TRAN TRAM ANH\n"
            f"💵 Số tiền: `{amount:,} VNĐ`\n"
            f"📝 Nội dung chuyển khoản: `NAP{user_id}{magd}`\n\n"
            f"⚠️ *Lưu ý:* Chuyển chính xác số tiền và nội dung trên. Sau khi chuyển xong, báo admin duyệt lệnh: `/duyệt {magd}`",
            parse_mode="Markdown"
        )

    elif data == "ls_nap":
        history = "\n".join(user["history_nap"]) if user["history_nap"] else "Chưa có lịch sử nạp tiền."
        await query.message.reply_text(f"📈 **LỊCH SỬ NẠP**\n\n{history}", parse_mode="Markdown")
    
    elif data == "ls_rut":
        history = "\n".join(user["history_rut"]) if user["history_rut"] else "Chưa có lịch sử rút tiền."
        await query.message.reply_text(f"📉 **LỊCH SỬ RÚT**\n\n{history}", parse_mode="Markdown")

    elif data == "ls_choi":
        history = "\n".join(user["history_choi"]) if user["history_choi"] else "Chưa có lịch sử chơi."
        await query.message.reply_text(f"📊 **LỊCH SỬ CHƠI (THẮNG/THUA)**\n\n{history}", parse_mode="Markdown")

    elif data == "vip_info":
        update_vip(user)
        await query.message.reply_text(
            f"👑 **QUẢN LÝ VIP & ĐỔI ĐIỂM**\n"
            f"- Cấp bậc: {user['vip_level']}\n"
            f"- Điểm tích lũy: {user['vip_points']} điểm (100k cược = 1 điểm)\n"
            f"- Lệnh đổi điểm: `/doidiemvip [số_điểm]` (1 điểm = 200đ)",
            parse_mode="Markdown"
        )

    elif data == "nhap_gc":
        await query.message.reply_text("💡 Hướng dẫn nhập giftcode:\nSoạn cú pháp: `/code [Mã_code]` để nhận thưởng vào số dư.")

    elif data == "mua_gc":
        await query.message.reply_text(
            "🎫 **HƯỚNG DẪN MUA GIFTCODE**\n"
            "- Yêu cầu: Tổng nạp tối thiểu `100.000 VNĐ`.\n"
            "- Phí giao dịch: `5%`.\n"
            "- Cú pháp: `/muagift [Số_lượng] [Mệnh_giá]`\n"
            "Ví dụ: `/muagift 1 10000`"
        )

    elif data == "hc_ngay":
        hoan_tien = int(user["total_bet"] * 0.004)
        user["balance"] += hoan_tien
        user["history_choi"].append(f"Nhận hoàn cược ngày: +{hoan_tien:,}đ")
        await query.message.reply_text(f"🎁 Nhận thành công hoàn cược ngày: `+{hoan_tien:,} VNĐ`!", parse_mode="Markdown")

    elif data == "hc_tuan":
        hoan_tien = int(user["total_bet"] * 0.004 * 7)
        user["balance"] += hoan_tien
        await query.message.reply_text(f"🎁 Nhận thành công hoàn cược tuần: `+{hoan_tien:,} VNĐ`!", parse_mode="Markdown")

    elif data == "ht_ngay" or data == "ht_tuan":
        await query.message.reply_text("🛡️ Hoàn thua ngày/tuần tự động quyết toán lúc 23:59 hàng ngày.")

    elif data == "ho_tro":
        await query.message.reply_text("🎧 Hỗ trợ trực tuyến 24/7 qua CSKH.")

    elif data == "nap_nganhang":
        magd = random.randint(100000, 999999)
        await query.message.reply_text(
            "➕ **THÔNG TIN CHUYỂN KHOẢN NẠP TIỀN**\n\n"
            "🏦 Ngân hàng: MBBANK\n"
            "📌 STK: `0328122738`\n"
            "💰 Chủ TK: TRAN TRAM ANH\n"
            f"📝 Nội dung: `NAP{user_id}{magd}`\n\n"
            "⚠️ *Lưu ý:* Nạp tối thiểu `50.000 VNĐ` để mở khóa, thoát trạng thái Tân thủ và bỏ giới hạn max cược 10k!\n"
            f"👉 Báo admin duyệt bằng lệnh: `/duyệt {magd}`",
            parse_mode="Markdown"
        )

    elif data == "choi_taixiu":
        await query.message.reply_text("🎲 Tham gia đặt cược trực tiếp tại nhóm: https://t.me/tuanhung88chat bằng cú pháp: `T [tiền]`, `X [tiền]`, `C [tiền]`, `L [tiền]`", parse_mode="Markdown")

    elif data == "choi_chanle":
        await query.message.reply_text("🎯 Tham gia đặt cược Chẵn Lẻ tại nhóm: https://t.me/tuanhung88chat bằng cú pháp: `C [tiền]` hoặc `L [tiền]`", parse_mode="Markdown")

# --- CÁC LỆNH QUẢN LÝ GIFTCODE & ADMIN ---
async def taocode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("⚠️ Sai cú pháp! Dùng: `/taocode [số_lượng] [tiền]`", parse_mode="Markdown")
        return
    try:
        soluong, tien = int(args[0]), int(args[1])
    except ValueError:
        await update.message.reply_text("⚠️ Số lượng và tiền phải là số nguyên!")
        return

    codes = []
    for _ in range(soluong):
        c = f"HIT{random.randint(100000, 999999)}"
        giftcode_db[c] = tien
        codes.append(c)

    await update.message.reply_text(f"✅ Tạo thành công {soluong} giftcode trị giá `{tien:,}đ`:\n`" + "\n".join(codes) + "`", parse_mode="Markdown")

async def themcode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("⚠️ Cú pháp: `/themcode [mã] [số_tiền]`")
        return
    code, tien = args[0], int(args[1])
    giftcode_db[code] = tien
    await update.message.reply_text(f"✅ Đã thêm mã `{code}` trị giá `{tien:,}đ`!", parse_mode="Markdown")

async def xoacode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Cú pháp: `/xoacode [mã]`")
        return
    code = args[0]
    if code in giftcode_db:
        del giftcode_db[code]
        await update.message.reply_text(f"🗑️ Đã xóa mã `{code}`.")
    else:
        await update.message.reply_text("❌ Không tìm thấy mã này trong hệ thống.")

async def danhsachcode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not giftcode_db:
        await update.message.reply_text("📂 Kho giftcode hiện đang trống.")
        return
    list_str = "\n".join([f"• `{k}`: {v:,}đ" for k, v in giftcode_db.items()])
    await update.message.reply_text(f"📂 **KHO GIFTCODE:**\n{list_str}", parse_mode="Markdown")

async def muagift_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    user_id = update.effective_user.id
    user = get_user(user_id)

    if len(args) < 2:
        await update.message.reply_text("⚠️ Cú pháp: `/muagift [số_lượng] [mệnh_giá]`", parse_mode="Markdown")
        return

    tong_nap = sum([int(x.split("đ")[0].replace("Nạp thành công ", "").replace(",", "")) for x in user["history_nap"] if "Nạp thành công" in x] or [0])
    if tong_nap < 100000:
        await update.message.reply_text("❌ Bạn cần tổng nạp tối thiểu `100.000 VNĐ` mới có thể mua giftcode!", parse_mode="Markdown")
        return

    try:
        soluong, menh_gia = int(args[0]), int(args[1])
    except ValueError:
        await update.message.reply_text("⚠️ Số lượng và mệnh giá phải là số!")
        return

    tong_goc = soluong * menh_gia
    phi = int(tong_goc * 0.05)
    tong_thanh_toan = tong_goc + phi

    if user["balance"] < tong_thanh_toan:
        await update.message.reply_text(f"❌ Số dư không đủ! Cần `{tong_thanh_toan:,}đ` (gồm 5% phí).")
        return

    user["balance"] -= tong_thanh_toan
    codes = []
    for _ in range(soluong):
        c = f"BUY{random.randint(10000, 99999)}"
        giftcode_db[c] = menh_gia
        codes.append(c)

    await update.message.reply_text(
        f"✅ **MUA GIFTCODE THÀNH CÔNG!**\n"
        f"- Tổng trừ (đã gồm 5% phí): `{tong_thanh_toan:,}đ`\n"
        f"- Mã của bạn (đã khóa riêng): `" + ", ".join(codes) + "`",
        parse_mode="Markdown"
    )

async def code_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not args:
        await update.message.reply_text("⚠️ Cú pháp: `/code [mã_giftcode]`", parse_mode="Markdown")
        return
    
    code = args[0]
    if code in giftcode_db:
        val = giftcode_db[code]
        user["balance"] += val
        del giftcode_db[code]
        await update.message.reply_text(f"🎉 **NHẬP GIFTCODE THÀNH CÔNG!**\n🎁 Nhận được: `+{val:,} VNĐ` vào số dư.", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Mã code không tồn tại hoặc đã được sử dụng!")

async def doidiemvip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not args:
        await update.message.reply_text(f"⚠️ Cú pháp: `/doidiemvip [số_điểm]`\n(Bạn đang có `{user['vip_points']}` điểm. 1 điểm = 200đ)", parse_mode="Markdown")
        return
    try:
        diem = int(args[0])
    except ValueError:
        await update.message.reply_text("⚠️ Số điểm phải là số nguyên!")
        return

    if diem > user["vip_points"] or diem <= 0:
        await update.message.reply_text("❌ Số điểm không hợp lệ hoặc vượt quá số điểm hiện có!")
        return

    tien_thuong = diem * 200
    user["vip_points"] -= diem
    user["balance"] += tien_thuong
    await update.message.reply_text(f"✅ Đổi thành công `{diem}` điểm VIP nhận `+{tien_thuong:,} VNĐ`!", parse_mode="Markdown")

async def chinhxucxac_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global forced_dice_result
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Bạn không có quyền sử dụng lệnh quản trị này!")
        return

    args = context.args
    if not args:
        await update.message.reply_text(
            "⚠️ Hướng dẫn lệnh chỉnh xúc xắc chuẩn xác 100% trong phiên:\n"
            "• `/chinhxucxac tai` (100% ra Tài)\n"
            "• `/chinhxucxac xiu` (100% ra Xỉu)\n"
            "• `/chinhxucxac reset` (Trở về ngẫu nhiên)"
        )
        return
    
    mode = args[0].lower()
    if mode == "tai":
        forced_dice_result = "TAI"
        await update.message.reply_text("⚡ Đã khóa kết quả: Phiên tiếp theo chuẩn xác 100% ra **TÀI**!")
    elif mode == "xiu":
        forced_dice_result = "XIU"
        await update.message.reply_text("⚡ Đã khóa kết quả: Phiên tiếp theo chuẩn xác 100% ra **XỈU**!")
    else:
        forced_dice_result = None
        await update.message.reply_text("🔄 Đã tắt hack, xúc xắc quay ngẫu nhiên bình thường.")

async def duyet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Bạn không có quyền duyệt nạp!")
        return

    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Cú pháp: `/duyệt [mã_nạp]`")
        return
    
    ma_nap = args[0]
    for u_id, u_data in users_db.items():
        u_data["is_newbie"] = False
        u_data["balance"] += 50000
        u_data["history_nap"].append(f"Nạp thành công 50,000đ (Mã: #{ma_nap})")
        break

    await update.message.reply_text(f"✅ Duyệt thành công mã nạp #{ma_nap}!\n✅ Đã cộng 50.000đ và **Thoát Tân Thủ** thành công (Mở khóa toàn bộ hạn mức).", parse_mode="Markdown")

# --- HÀM KHỞI CHẠY CHÍNH ---
TOKEN = "9286450426:AAHYoubtmQirYbLnmmN309OeA81sABUrxsA"

async def main_async():
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Đăng ký các lệnh
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("caidatbank", caidatbank_command))
    application.add_handler(CommandHandler("rut", rut_command))
    application.add_handler(CommandHandler("duyet", duyet_command))
    application.add_handler(CommandHandler("taocode", taocode_command))
    application.add_handler(CommandHandler("themcode", themcode_command))
    application.add_handler(CommandHandler("xoacode", xoacode_command))
    application.add_handler(CommandHandler("danhsachcode", danhsachcode_command))
    application.add_handler(CommandHandler("muagift", muagift_command))
    application.add_handler(CommandHandler("code", code_command))
    application.add_handler(CommandHandler("nhapcode", code_command))
    application.add_handler(CommandHandler("doidiemvip", doidiemvip_command))
    application.add_handler(CommandHandler("chinhxucxac", chinhxucxac_command))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    
    # Giữ bot chạy liên tục
    stop_signal = asyncio.get_running_loop().create_future()
    await stop_signal

def main():
    try:
        asyncio.run(main_async())
    except (KeyboardInterrupt, SystemExit):
        pass

if __name__ == "__main__":
    main()
