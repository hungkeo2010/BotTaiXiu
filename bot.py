import nest_asyncio
nest_asyncio.apply()
import logging
import random
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

# Biến toàn cục quản lý can thiệp xúc xắc 100% chính xác trong phiên
forced_dice_result = None

def get_user(user_id):
    if user_id not in users_db:
        users_db[user_id] = {
            "balance": 0,
            "total_bet": 0,
            "vip_points": 0,
            "vip_level": "Đồng 🥉",
            "is_newbie": True,  # Mặc định tài khoản mới là Tân thủ (Max cược 10k, cần nạp 50k mở khóa)
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
        f"🤖 **HỆ THỐNG BOT TÀI XỈU VIP 24/7**\n\n"
        f"🆔 ID của bạn: `{user_id}`\n"
        f"💡 Trạng thái: **Tân thủ** (Giới hạn cược max 10k. Nạp tối thiểu 50k để thoát Tân thủ và mở khóa toàn bộ hệ thống!)\n\n"
        f"Vui lòng chọn các tính năng bên dưới menu:"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=get_main_menu())

# --- XỬ LÝ NHẮN TIN MENU CHÍNH ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    user = get_user(user_id)

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
        keyboard = [[InlineKeyboardButton("🏦 Chuyển khoản ngân hàng", callback_data="nap_nganhang")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("💲 **CHỌN PHƯƠNG THỨC NẠP TIỀN**", parse_mode="Markdown", reply_markup=reply_markup)

    elif text == "📁 Danh sách game":
        keyboard = [
            [InlineKeyboardButton("🎲 Tài Xỉu Siêu Tốc (Nổ hũ X5)", callback_data="choi_taixiu"), InlineKeyboardButton("🎯 Chẵn Lẻ / Lót Vị", callback_data="choi_chanle")]
        ]
        await update.message.reply_text("🎮 **DANH SÁCH TRÒ CHƠI**\nChọn game bạn muốn tham gia:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif text == "💳 Rút Tiền":
        await update.message.reply_text("💳 Vui lòng liên hệ CSKH hoặc dùng lệnh rút tiền tự động.")

    elif text == "🌸 Chuyển Tiền":
        await update.message.reply_text("🌸 Cú pháp chuyển tiền: `/chuyentien [ID_nhận] [Số_tiền]`")

    elif text == "🚀 Dua top":
        await update.message.reply_text("🚀 **BẢNG XẾP HẠNG ĐUA TOP**\n1. Chưa có dữ liệu tuần này.")

    elif text == "🎁 Event":
        await update.message.reply_text("🎁 Nhận code miễn phí mỗi ngày tại kênh thông báo sự kiện.")

    elif text == "🔍 Lệnh":
        help_text = (
            "🔍 **HỆ THỐNG LỆNH HỖ TRỢ**\n\n"
            "👤 **Thành viên:**\n"
            "• `/muagift [số_lượng] [mệnh_giá]` - Mua giftcode (Phí 5%, tổng nạp 100k)\n"
            "• `/code [mã_code]` - Nhập giftcode nhận tiền\n"
            "• `/doidiemvip [số_điểm]` - Đổi điểm VIP (1 điểm = 200đ)\n"
            "• `/chuyentien [id] [số_tiền]` - Chuyển khoản nội bộ\n\n"
            "👑 **Admin / Chủ Bot:**\n"
            "• `/taocode [số_lượng] [tiền]` - Tạo nhanh giftcode\n"
            "• `/themcode [mã] [tiền]` - Thêm mã tùy chỉnh\n"
            "• `/xoacode [mã]` - Xóa mã trong kho\n"
            "• `/danhsachcode` - Xem danh sách giftcode\n"
            "• `/chinhxucxac [tai/xiu/reset]` - Hack kết quả chuẩn 100%\n"
            "• `/duyệt [mã_nạp]` - Duyệt nạp tiền & mở khóa Tân thủ"
        )
        await update.message.reply_text(help_text, parse_mode="Markdown")

# --- XỬ LÝ NÚT INLINE & GAME ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global forced_dice_result
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    data = query.data

    if data == "ls_nap":
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
        await query.message.reply_text(
            "➕ **THÔNG TIN CHUYỂN KHOẢN NẠP TIỀN**\n\n"
            "🏦 Ngân hàng: MBBANK\n"
            "📌 STK: `8328122728`\n"
            "💰 Chủ TK: TRAN TRAM ANH\n"
            "📝 Nội dung: `NAP8682451039`\n\n"
            "⚠️ *Lưu ý:* Nạp tối thiểu `50.000 VNĐ` để mở khóa, thoát trạng thái Tân thủ và bỏ giới hạn max cược 10k!\n"
            "👉 Báo admin duyệt bằng lệnh: `/duyệt [mã_giao_dịch]`",
            parse_mode="Markdown"
        )

    elif data == "choi_taixiu":
        # CHƠI TÀI XỈU - TÍCH HỢP HACK CHUẨN XÁC 100% & NỔ HŨ X5 KHI RA (3,6) HOẶC (3,1)
        if forced_dice_result == "TAI":
            dices = (5, 5, 6)  # Tổng 16 -> TÀI 100%
        elif forced_dice_result == "XIU":
            dices = (1, 2, 3)  # Tổng 6 -> XỈU 100%
        else:
            dices = (random.randint(1, 6), random.randint(1, 6), random.randint(1, 6))

        tong = sum(dices)
        ket_qua = "TÀI" if tong >= 11 else "XỈU"
        
        # Kiểm tra điều kiện nổ hũ X5 (nếu có xuất hiện cặp số 3 và 6, hoặc 3 và 1 trong kết quả xúc xắc)
        has_3_6 = (3 in dices and 6 in dices)
        has_3_1 = (3 in dices and 1 in dices)
        
        bet_amount = 10000  # Mức cược mô phỏng trong phiên chơi
        no_hu_text = ""
        if has_3_6 or has_3_1:
            thuong_no_hu = bet_amount * 5
            user["balance"] += thuong_no_hu
            no_hu_text = f"\n\n🎉 **NỔ HŨ CỰC LỚN!** Xúc xắc xuất hiện bộ đặc biệt -> **NHÂN X5 TIỀN THƯỞNG** (+{thuong_no_hu:,}đ)!"

        if user["is_newbie"]:
            notif = (
                f"🎲 **KẾT QUẢ TÀI XỈU (Tân thủ)**\n"
                f"🎲 Xúc xắc: {dices[0]} - {dices[1]} - {dices[2]} (Tổng: {tong} -> **{ket_qua}**)"
                f"{no_hu_text}\n\n⚠️ Bạn đang là Tân thủ (Max cược 10k). Hãy nạp 50k để mở khóa toàn bộ!"
            )
        else:
            notif = (
                f"🎲 **KẾT QUẢ TÀI XỈU VIP**\n"
                f"🎲 Xúc xắc: {dices[0]} - {dices[1]} - {dices[2]} (Tổng: {tong} -> **{ket_qua}**)"
                f"{no_hu_text}"
            )
        
        user["history_choi"].append(f"Tài Xỉu: {dices} ({ket_qua})")
        await query.message.reply_text(notif, parse_mode="Markdown")

    elif data == "choi_chanle":
        await query.message.reply_text("🎯 **CHẮN LẺ & LÓT VỊ**\nVí dụ: D3 11 2k-5k (Dự đoán vị trí chuẩn xác, trúng x5 tiền thưởng!).")

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
    phi = int(tong_goc * 0.05)  # Phí 5%
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
        del giftcode_db[code]  # Dùng xong tự động khóa/xóa
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
    
    ma_nạp = args[0]
    for u_id, u_data in users_db.items():
        u_data["is_newbie"] = False  # Thoát Tân thủ
        u_data["balance"] += 50000
        u_data["history_nap"].append(f"Nạp thành công 50,000đ (Mã: #{ma_nạp})")
        break

    await update.message.reply_text(f"✅ Duyệt thành công mã nạp #{ma_nạp}!\n✅ Đã cộng 50.000đ và **Thoát Tân Thủ** thành công (Mở khóa toàn bộ hạn mức cược)!")

def main():
    # THAY THẾ "YOUR_TOKEN_HERE" BẰNG TOKEN BOT TELEGRAM THẬT CỦA BẠN
    TOKEN = "9286450426:AAHYoubtmQirYbLnmmN309OeA81sABUrxsA"
    
    application = ApplicationBuilder().token(TOKEN).build()

    # Đăng ký các lệnh
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("duyet", duyet_command))
    application.add_handler(CommandHandler("taocode", taocode_command))
    application.add_handler(CommandHandler("themcode", themcode_command))
    application.add_handler(CommandHandler("xoacode", xoacode_command))
    application.add_handler(CommandHandler("danhsachcode", danhsachcode_command))
    application.add_handler(CommandHandler("muagift", muagift_command))
    application.add_handler(CommandHandler("code", code_command))
    application.add_handler(CommandHandler("doidiemvip", doidiemvip_command))
    application.add_handler(CommandHandler("chinhxucxac", chinhxucxac_command))
    
    # Xử lý tin nhắn và nút bấm
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    if __name__ == "__main__":
    import asyncio
    asyncio.run(main())




    
