import os
import io
import logging
import random
import string
from datetime import datetime
from typing import Dict, Any, Optional

from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ==================== CONFIGURATION ====================

# Get bot token from environment variable
TOKEN = os.environ.get("TOKEN") or os.environ.get("BOT_TOKEN")

if not TOKEN:
    raise ValueError("❌ No TOKEN found! Please set TOKEN environment variable.")

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ==================== CONSTANTS ====================

# Supported formats for image conversion
SUPPORTED_FORMATS = {
    "jpg": {"name": "JPEG", "extension": "jpg", "mime": "image/jpeg"},
    "jpeg": {"name": "JPEG", "extension": "jpg", "mime": "image/jpeg"},
    "png": {"name": "PNG", "extension": "png", "mime": "image/png"},
    "webp": {"name": "WEBP", "extension": "webp", "mime": "image/webp"},
    "gif": {"name": "GIF", "extension": "gif", "mime": "image/gif"},
    "bmp": {"name": "BMP", "extension": "bmp", "mime": "image/bmp"},
    "ico": {"name": "ICO", "extension": "ico", "mime": "image/x-icon"},
    "tiff": {"name": "TIFF", "extension": "tiff", "mime": "image/tiff"},
    "pdf": {"name": "PDF", "extension": "pdf", "mime": "application/pdf"},
}

MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20MB
USER_DATA: Dict[int, Dict[str, Any]] = {}
URLS_DB: Dict[str, str] = {}  # In-memory URL storage

# ==================== HELPER FUNCTIONS ====================

def get_image_format(image_bytes: bytes) -> str:
    """Detect image format from bytes."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        return img.format.lower() if img.format else "unknown"
    except Exception as e:
        logger.error(f"Format detection error: {e}")
        return "unknown"

def generate_short_code(length: int = 6) -> str:
    """Generate a random short code for URL shortening."""
    chars = string.ascii_letters + string.digits
    code = ''.join(random.choices(chars, k=length))
    # Ensure code is unique
    while code in URLS_DB:
        code = ''.join(random.choices(chars, k=length))
    return code

async def convert_image(image_bytes: bytes, target_format: str) -> bytes:
    """
    Convert image to target format.
    
    Args:
        image_bytes: Raw image data
        target_format: Target format (jpg, png, webp, etc.)
    
    Returns:
        Converted image bytes
    """
    # Open image
    img = Image.open(io.BytesIO(image_bytes))
    
    # Convert RGBA to RGB for JPEG (remove alpha channel)
    if target_format.lower() in ["jpg", "jpeg"]:
        if img.mode == "RGBA":
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background
        elif img.mode not in ["RGB", "L"]:
            img = img.convert("RGB")
    
    # Handle ICO format (requires specific sizes)
    if target_format.lower() == "ico":
        output = io.BytesIO()
        sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128)]
        img.save(output, format="ICO", sizes=sizes)
        return output.getvalue()
    
    # Handle PDF conversion
    if target_format.lower() == "pdf":
        output = io.BytesIO()
        img.save(output, format="PDF", resolution=100.0)
        return output.getvalue()
    
    # Regular image conversion
    output = io.BytesIO()
    format_name = target_format.upper()
    
    # Optimize save parameters
    save_kwargs = {}
    if target_format.lower() in ["jpg", "jpeg"]:
        save_kwargs = {"quality": 92, "optimize": True, "progressive": True}
    elif target_format.lower() == "png":
        save_kwargs = {"optimize": True, "compress_level": 6}
    elif target_format.lower() == "webp":
        save_kwargs = {"quality": 90, "lossless": False}
    elif target_format.lower() == "gif":
        save_kwargs = {"optimize": True}
    elif target_format.lower() == "tiff":
        save_kwargs = {"compression": "tiff_lzw"}
    
    img.save(output, format=format_name, **save_kwargs)
    return output.getvalue()

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Create the main menu keyboard."""
    keyboard = [
        [InlineKeyboardButton("🔄 Convert Image", callback_data="image_mode")],
        [InlineKeyboardButton("🔗 Shorten URL", callback_data="shorten")],
        [InlineKeyboardButton("📝 Count Words", callback_data="count")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_format_selection_keyboard() -> InlineKeyboardMarkup:
    """Create format selection keyboard."""
    keyboard = [
        [InlineKeyboardButton("🖼️ JPG", callback_data="jpg"),
         InlineKeyboardButton("🖼️ PNG", callback_data="png")],
        [InlineKeyboardButton("🖼️ WEBP", callback_data="webp"),
         InlineKeyboardButton("🖼️ GIF", callback_data="gif")],
        [InlineKeyboardButton("🖼️ BMP", callback_data="bmp"),
         InlineKeyboardButton("🖼️ ICO", callback_data="ico")],
        [InlineKeyboardButton("🖼️ TIFF", callback_data="tiff"),
         InlineKeyboardButton("📄 PDF", callback_data="pdf")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==================== BOT COMMANDS ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user = update.effective_user
    welcome_text = f"""
👋 **Hello {user.first_name}!**

Welcome to **PixelPressBot** - Your All-in-One Image & Tool Assistant! 🎨

🔄 **What I can do:**

📸 **Image Tools:**
• Convert images between formats (JPG, PNG, WEBP, GIF, BMP, ICO, TIFF, PDF)
• High quality output with optimized sizes

🔗 **URL Tools:**
• Shorten long URLs instantly
• Generate unique short codes

📝 **Text Tools:**
• Count words, characters, sentences, and paragraphs
• Analyze text statistics

📝 **Commands:**
/start - Show this message
/help - Get detailed help
/menu - Show main menu
/about - About this bot
/cancel - Cancel current operation

Let's get started! Use /menu or send me an image. 🚀
"""
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    help_text = """
📖 **Help Guide - PixelPressBot**

🔹 **Image Converter:**
1. Send me an image or use /menu and select "Convert Image"
2. Choose your desired format from the buttons
3. I'll convert and send it back!

🔹 **URL Shortener:**
1. Use /menu and select "Shorten URL"
2. Send the URL you want to shorten
3. Get your shortened link!

🔹 **Word Counter:**
1. Use /menu and select "Count Words"
2. Send the text you want to count
3. Get detailed statistics!

🎯 **Supported Image Formats:**
• JPG / JPEG
• PNG
• WEBP
• GIF
• BMP
• ICO (Icon)
• TIFF
• PDF

⚡ **Tips:**
• Maximum image size: 20MB
• All processing is done securely
• Your data is private
• Use /cancel to stop any operation

🔗 **Commands:**
/start - Welcome message
/help - This help guide
/menu - Show main menu
/about - Bot information
/cancel - Cancel current operation
"""
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /menu command."""
    reply_markup = get_main_menu_keyboard()
    await update.message.reply_text(
        "🎯 **Main Menu**\n\nSelect an option below:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /about command."""
    about_text = """
🤖 **PixelPressBot v1.0**

🎨 **Your All-in-One Image & Tool Assistant**

✨ **Features:**
• Convert images between 8+ formats
• Shorten URLs instantly
• Count words and characters
• User-friendly buttons
• High-quality output
• Secure processing

🛠️ **Built with:**
• Python 3.11+
• python-telegram-bot
• Pillow (PIL)

🚀 **Hosted on:** Railway

📅 **Created:** 2024

👨‍💻 **Open Source**
Contributions welcome on GitHub!

📢 **Use /menu to get started!**
"""
    await update.message.reply_text(about_text, parse_mode="Markdown")

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cancel command to clear user data."""
    user_id = update.effective_user.id
    if user_id in USER_DATA:
        del USER_DATA[user_id]
        await update.message.reply_text(
            "✅ **Operation cancelled.**\n\nUse /menu to start a new operation.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "ℹ️ No active operation to cancel.\n\nUse /menu to get started!",
            parse_mode="Markdown"
        )

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle unknown commands."""
    keyboard = [
        [InlineKeyboardButton("🎯 Main Menu", callback_data="menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "❌ Unknown command.\n\n"
        "Use /start, /help, /menu, /about, or /cancel.\n"
        "Or tap the button below to get started!",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# ==================== IMAGE HANDLER ====================

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming images."""
    user_id = update.effective_user.id
    
    # Get the largest photo
    photo = update.message.photo[-1]
    file = await photo.get_file()
    
    # Check file size
    if file.file_size > MAX_IMAGE_SIZE:
        await update.message.reply_text(
            f"❌ **Image too large!**\n\n"
            f"Size: {file.file_size // 1024 // 1024}MB\n"
            f"Maximum allowed: {MAX_IMAGE_SIZE // 1024 // 1024}MB\n\n"
            "Please send a smaller image.",
            parse_mode="Markdown"
        )
        return
    
    # Download image
    try:
        image_bytes = await file.download_as_bytearray()
        image_bytes = bytes(image_bytes)
    except Exception as e:
        logger.error(f"Failed to download image: {e}")
        await update.message.reply_text(
            "❌ **Failed to download image.**\n\nPlease try again.",
            parse_mode="Markdown"
        )
        return
    
    # Detect original format
    original_format = get_image_format(image_bytes)
    
    # Store in user data
    USER_DATA[user_id] = {
        "image_bytes": image_bytes,
        "original_format": original_format,
        "timestamp": datetime.now(),
        "mode": "image_conversion"
    }
    
    # Send format selection
    original_display = original_format.upper() if original_format != "unknown" else "Unknown"
    reply_markup = get_format_selection_keyboard()
    
    await update.message.reply_text(
        f"🔄 **Choose conversion format**\n\n"
        f"📂 **Original:** `{original_display}`\n"
        f"📏 **Size:** {len(image_bytes) // 1024}KB\n"
        f"📅 **Received:** {datetime.now().strftime('%H:%M:%S')}\n\n"
        f"Select your desired format:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# ==================== TEXT HANDLER ====================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages."""
    user_id = update.effective_user.id
    text = update.message.text
    
    # Check if user is in URL shortening mode
    if user_id in USER_DATA and USER_DATA[user_id].get("mode") == "url_shortening":
        # Validate URL
        if not text.startswith(("http://", "https://")):
            keyboard = [
                [InlineKeyboardButton("🔗 Try Again", callback_data="shorten")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "❌ **Invalid URL!**\n\n"
                "Please send a valid URL starting with http:// or https://\n\n"
                "Example: `https://example.com/very/long/url`",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            return
        
        # Generate short code
        short_code = generate_short_code()
        URLS_DB[short_code] = text
        
        # Create shortened URL
        short_url = f"https://pixelpressbot.com/{short_code}"
        
        keyboard = [
            [InlineKeyboardButton("🔗 Shorten Another", callback_data="shorten")],
            [InlineKeyboardButton("🎯 Main Menu", callback_data="menu")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ **URL Shortened!**\n\n"
            f"🔗 **Original:**\n`{text}`\n\n"
            f"📎 **Shortened:**\n`{short_url}`\n\n"
            f"📝 **Code:** `{short_code}`\n"
            f"📅 **Created:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"💡 Use /shorten again to shorten another URL!",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
        # Clean up user data
        if user_id in USER_DATA:
            del USER_DATA[user_id]
        return
    
    # Check if user is in word count mode
    if user_id in USER_DATA and USER_DATA[user_id].get("mode") == "word_count":
        # Count words, characters, sentences, paragraphs
        words = len(text.split())
        characters = len(text)
        characters_no_spaces = len(text.replace(" ", ""))
        sentences = len([s for s in text.split(".") if s.strip()]) + len([s for s in text.split("!") if s.strip()]) + len([s for s in text.split("?") if s.strip()])
        paragraphs = len([p for p in text.split("\n\n") if p.strip()]) if "\n\n" in text else 1
        
        keyboard = [
            [InlineKeyboardButton("📝 Count Another", callback_data="count")],
            [InlineKeyboardButton("🎯 Main Menu", callback_data="menu")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"📝 **Text Analysis Results**\n\n"
            f"📊 **Statistics:**\n"
            f"• **Words:** `{words}`\n"
            f"• **Characters:** `{characters}`\n"
            f"• **Characters (no spaces):** `{characters_no_spaces}`\n"
            f"• **Sentences:** `{sentences}`\n"
            f"• **Paragraphs:** `{paragraphs}`\n\n"
            f"📅 **Analyzed:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
        # Clean up user data
        if user_id in USER_DATA:
            del USER_DATA[user_id]
        return
    
    # If no mode set, show main menu
    reply_markup = get_main_menu_keyboard()
    await update.message.reply_text(
        "📝 **What would you like to do?**\n\n"
        f"Your message:\n`{text[:100]}{'...' if len(text) > 100 else ''}`\n\n"
        "Select an option below:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# ==================== CALLBACK HANDLER ====================

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    # Handle cancel
    if data == "cancel":
        if user_id in USER_DATA:
            del USER_DATA[user_id]
        await query.edit_message_text(
            "❌ **Operation cancelled.**\n\nUse /menu to start a new operation.",
            parse_mode="Markdown"
        )
        return
    
    # Handle menu
    if data == "menu":
        reply_markup = get_main_menu_keyboard()
        await query.edit_message_text(
            "🎯 **Main Menu**\n\nSelect an option below:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return
    
    # Handle help
    if data == "help":
        help_text = """
📖 **Help Guide - PixelPressBot**

🔹 **Image Converter:**
• Send me an image or use /menu
• Choose your desired format
• Get your converted image!

🔹 **URL Shortener:**
• Use /menu and select "Shorten URL"
• Send the URL you want to shorten
• Get your shortened link!

🔹 **Word Counter:**
• Use /menu and select "Count Words"
• Send the text you want to count
• Get detailed statistics!

🎯 **Supported Formats:**
JPG, PNG, WEBP, GIF, BMP, ICO, TIFF, PDF

💡 **Use /cancel** to stop any operation
        """
        await query.edit_message_text(help_text, parse_mode="Markdown")
        return
    
    # Handle image mode
    if data == "image_mode":
        # Clear any existing data
        if user_id in USER_DATA:
            del USER_DATA[user_id]
        
        await query.edit_message_text(
            "📸 **Image Converter**\n\n"
            "Please send me an image to convert.\n\n"
            "I support: JPG, PNG, WEBP, GIF, BMP, ICO, TIFF, and PDF.\n\n"
            "📏 Maximum size: 20MB",
            parse_mode="Markdown"
        )
        return
    
    # Handle shorten
    if data == "shorten":
        USER_DATA[user_id] = {"mode": "url_shortening"}
        await query.edit_message_text(
            "🔗 **URL Shortener**\n\n"
            "Please send me the URL you want to shorten.\n\n"
            "Example: `https://example.com/very/long/url`\n\n"
            "💡 Make sure it starts with http:// or https://",
            parse_mode="Markdown"
        )
        return
    
    # Handle count
    if data == "count":
        USER_DATA[user_id] = {"mode": "word_count"}
        await query.edit_message_text(
            "📝 **Word Counter**\n\n"
            "Please send me the text you want to count.\n\n"
            "I'll count:\n"
            "• Words\n"
            "• Characters\n"
            "• Sentences\n"
            "• Paragraphs\n\n"
            "💡 Send any text to analyze!",
            parse_mode="Markdown"
        )
        return
    
    # Handle image conversion (format selection)
    if data in SUPPORTED_FORMATS:
        selected_format = data
        
        # Check if user has stored image
        if user_id not in USER_DATA or "image_bytes" not in USER_DATA[user_id]:
            await query.edit_message_text(
                "⚠️ **No image found!**\n\n"
                "Please send an image first, then choose a format.\n\n"
                "Use /menu and select 'Convert Image' to start again.",
                parse_mode="Markdown"
            )
            return
        
        # Get user data
        user_info = USER_DATA[user_id]
        image_bytes = user_info["image_bytes"]
        original_format = user_info.get("original_format", "unknown")
        
        # Update message to show processing
        await query.edit_message_text(
            f"🔄 **Converting to {selected_format.upper()}...**\n\n"
            f"⏳ Please wait, this may take a moment.\n\n"
            f"📂 Original: `{original_format.upper()}`\n"
            f"📂 Target: `{selected_format.upper()}`",
            parse_mode="Markdown"
        )
        
        try:
            # Convert image
            converted_bytes = await convert_image(image_bytes, selected_format)
            
            # Prepare filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            extension = SUPPORTED_FORMATS.get(selected_format, {}).get("extension", selected_format)
            filename = f"converted_{timestamp}.{extension}"
            
            # Send converted file
            caption = (
                f"✅ **Conversion Complete!**\n\n"
                f"📂 Original: `{original_format.upper()}`\n"
                f"📂 New: `{selected_format.upper()}`\n"
                f"📏 Size: {len(converted_bytes) // 1024}KB\n"
                f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            # Send as document for better handling
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=io.BytesIO(converted_bytes),
                filename=filename,
                caption=caption,
                parse_mode="Markdown"
            )
            
            # Send additional options
            keyboard = [
                [InlineKeyboardButton("🔄 Convert Another", callback_data="image_mode")],
                [InlineKeyboardButton("🎯 Main Menu", callback_data="menu")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="🔄 **What would you like to do next?**",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            
            # Clean up user data
            if user_id in USER_DATA:
                del USER_DATA[user_id]
            
        except Exception as e:
            logger.error(f"Conversion error: {str(e)}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=(
                    f"❌ **Conversion Failed!**\n\n"
                    f"Error: `{str(e)}`\n\n"
                    f"Please try again with a different format or image.\n"
                    f"Use /menu to start over."
                ),
                parse_mode="Markdown"
            )

# ==================== ERROR HANDLER ====================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors."""
    logger.error(f"Update {update} caused error: {context.error}")
    
    if update and update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                "❌ **An error occurred!**\n\n"
                "Please try again later.\n"
                "If the issue persists, use /cancel to reset.\n\n"
                "Use /menu to start a new operation."
            ),
            parse_mode="Markdown"
        )

# ==================== MAIN FUNCTION ====================

def main() -> None:
    """Start the bot."""
    logger.info("🚀 Starting PixelPressBot...")
    
    # Build application
    application = Application.builder().token(TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    
    # Add message handlers
    application.add_handler(MessageHandler(filters.PHOTO, handle_image))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Add callback handler
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start bot
    logger.info("✅ Bot is running and listening for messages...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
