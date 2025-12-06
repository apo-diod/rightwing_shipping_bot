import logging
from datetime import datetime, timedelta
from collections import defaultdict, deque
import random
import json
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

compatibility_mapping = {
    (0, 9): ["☠️", "💀", "😭", "🚷", "⛔"],
    (10, 29): ["🌪️", "💥", "🆘", "😬", "⚠️"],
    (30, 49): ["🤨", "🤔", "💬", "🎭"],
    (50, 68): ["💛", "🤝", "🙂", "☯️", "⚖️"],
    (69, 69): ["🙃", "😈", "🌚"],
    (70, 84): ["❤️", "👍", "🔥", "😊", "💑"],
    (85, 94): ['💕', "😍", "🌹", "🤩", "🌈"],
    (95, 100): ["💘", "🥰", "✨", "🌟", "💞", "💖"]
}

def map_compatibility_emoji(compatibiility):
    for key in compatibility_mapping.keys():
        if compatibiility in range(key[0], key[1]+1):
            return random.choice(compatibility_mapping[key])
    return "😑"

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Data storage
DATA_FILE = 'data/shipping_data.json'

class ShippingBot:
    def __init__(self):
        # group_id -> misc_data
        self.shipping_data = dict()
        # group_id -> deque of user_ids (last 500)
        self.user_lists = defaultdict(lambda: deque(maxlen=500))
        
        # group_id -> (user_id_1, user_id_2, compatibility)
        self.current_pairs = {}
        
        # group_id -> datetime of last shipping
        self.last_shipping = {}
        
        # group_id -> set of user_ids who voted to reset
        self.reset_votes = defaultdict(set)
        
        # group_id -> user_id of person who initiated current ship
        self.current_shipper = {}
        
        # group_id -> {user_id: count} - successful ships initiated
        self.shipper_stats = defaultdict(lambda: defaultdict(int))
        
        # group_id -> {user_id: count} - times being shipped
        self.shipped_stats = defaultdict(lambda: defaultdict(int))
        
        self.load_data()
    
    def load_data(self):
        """Load data from file"""
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r') as f:
                    data = json.load(f)
                    
                # Restore user lists
                for group_id, users in data.get('user_lists', {}).items():
                    self.user_lists[int(group_id)] = deque(users, maxlen=500)
                
                # Restore current pairs
                for group_id, pair in data.get('current_pairs', {}).items():
                    self.current_pairs[int(group_id)] = tuple(pair) if len(pair) <= 2 else tuple(pair[:2])
                
                # Restore last shipping times
                for group_id, timestamp in data.get('last_shipping', {}).items():
                    self.last_shipping[int(group_id)] = datetime.fromisoformat(timestamp)
                
                # Restore current shipper
                for group_id, shipper_id in data.get('current_shipper', {}).items():
                    self.current_shipper[int(group_id)] = shipper_id
                
                # Restore shipper stats
                for group_id, stats in data.get('shipper_stats', {}).items():
                    self.shipper_stats[int(group_id)] = defaultdict(int, {int(k): v for k, v in stats.items()})
                
                # Restore shipped stats
                for group_id, stats in data.get('shipped_stats', {}).items():
                    self.shipped_stats[int(group_id)] = defaultdict(int, {int(k): v for k, v in stats.items()})
                
                # Restore shipping data
                self.shipping_data = {int(group_id): ship_data for group_id, ship_data in data.get('shipping_data', {}).items()}
                logger.info("Data loaded successfully")
            except Exception as e:
                logger.error(f"Error loading data: {e}")
    
    def save_data(self):
        """Save data to file"""
        try:
            data = {
                'user_lists': {
                    str(group_id): list(users) 
                    for group_id, users in self.user_lists.items()
                },
                'current_pairs': {
                    str(group_id): list(pair) 
                    for group_id, pair in self.current_pairs.items()
                },
                'last_shipping': {
                    str(group_id): timestamp.isoformat() 
                    for group_id, timestamp in self.last_shipping.items()
                },
                'current_shipper': {
                    str(group_id): shipper_id
                    for group_id, shipper_id in self.current_shipper.items()
                },
                'shipper_stats': {
                    str(group_id): {str(k): v for k, v in stats.items()}
                    for group_id, stats in self.shipper_stats.items()
                },
                'shipped_stats': {
                    str(group_id): {str(k): v for k, v in stats.items()}
                    for group_id, stats in self.shipped_stats.items()
                }
            }
            
            with open(DATA_FILE, 'w') as f:
                json.dump(data, f, indent=2)
                
            logger.info("Data saved successfully")
        except Exception as e:
            logger.error(f"Error saving data: {e}")
    
    def add_user(self, group_id: int, user_id: int):
        """Add user to the group's list"""
        logger.info(f'Adding user {user_id} to the list')
        users = self.user_lists[group_id]
        # Remove if exists (to update position)
        if user_id in users:
            users.remove(user_id)
        users.append(user_id)
        self.save_data()
    
    def get_shipping_data(self, group_id: int):
        return self.shipping_data.get(group_id, dict())

    def get_unique_users(self, group_id: int):
        """Get unique users from the list"""
        return list(set(self.user_lists[group_id]))
    
    async def can_ship(self, group_id: int, context) -> tuple[bool, str]:
        """Check if shipping is available"""
        if group_id in self.last_shipping:
            time_passed = datetime.now() - self.last_shipping[group_id]
            if time_passed < timedelta(hours=24):
                remaining = timedelta(hours=24) - time_passed
                hours = remaining.seconds // 3600
                minutes = (remaining.seconds % 3600) // 60
                user1_id, user2_id, _ = bot_data.current_pairs[group_id]
                status_msg = ""
                try:
                    user1 = await context.bot.get_chat_member(group_id, user1_id)
                    user2 = await context.bot.get_chat_member(group_id, user2_id)
                    
                    # Get full name (first name + last name if available)
                    user1_name = user1.user.first_name
                    if user1.user.last_name:
                        user1_name += f" {user1.user.last_name}"
                    
                    user2_name = user2.user.first_name
                    if user2.user.last_name:
                        user2_name += f" {user2.user.last_name}"
                    
                    status_msg += f"💑 Current ship:\n"
                    status_msg += f"{user1_name} ❤️ {user2_name}\n\n"
                except Exception as e:
                    logger.error(f"Error getting user info: {e}")
                    status_msg += f"💑 Current ship:\n"
                    status_msg += f"User {user1_id} ❤️ User {user2_id}\n\n"
                return False, f"⏰ Shipping is on cooldown! Time remaining: {hours}h {minutes}m\n" + status_msg
        
        unique_users = self.get_unique_users(group_id)
        if len(unique_users) < 2:
            return False, "❌ Need at least 2 different users in the chat to ship!"
        
        return True, ""
    
    def create_ship(self, group_id: int, shipper_id: int) -> tuple[int, int]:
        """Create a random ship pair"""
        unique_users = self.get_unique_users(group_id)
        user1, user2 = random.sample(unique_users, 2)
        
        compatibility = random.randint(0, 100)

        self.current_pairs[group_id] = (user1, user2)
        self.shipping_data[group_id] = dict()
        self.last_shipping[group_id] = datetime.now()
        self.current_shipper[group_id] = shipper_id
        self.reset_votes[group_id].clear()
        
        # Increment stats
        self.shipper_stats[group_id][shipper_id] += 1
        self.shipped_stats[group_id][user1] += 1
        self.shipped_stats[group_id][user2] += 1

        self.shipping_data[group_id]['compatibility'] = compatibility
        self.shipping_data[group_id]['compatibility_emoji'] = map_compatibility_emoji(compatibility)
        
        self.save_data()
        
        return user1, user2, compatibility
    
    def reset_ship(self, group_id: int):
        """Reset the current ship and revert stats"""
        if group_id in self.current_pairs:
            # Revert stats
            if group_id in self.current_shipper:
                shipper_id = self.current_shipper[group_id]
                self.shipper_stats[group_id][shipper_id] -= 1
                if self.shipper_stats[group_id][shipper_id] <= 0:
                    del self.shipper_stats[group_id][shipper_id]
            
            user1_id, user2_id, _ = self.current_pairs[group_id]
            self.shipped_stats[group_id][user1_id] -= 1
            self.shipped_stats[group_id][user2_id] -= 1
            
            if self.shipped_stats[group_id][user1_id] <= 0:
                del self.shipped_stats[group_id][user1_id]
            if self.shipped_stats[group_id][user2_id] <= 0:
                del self.shipped_stats[group_id][user2_id]
            
            del self.current_pairs[group_id]
        
        if group_id in self.current_shipper:
            del self.current_shipper[group_id]
        
        if group_id in self.last_shipping:
            del self.last_shipping[group_id]
        
        self.reset_votes[group_id].clear()
        self.save_data()

# Initialize bot data
bot_data = ShippingBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    logger.info("Received start command")
    await update.message.reply_text(
        "💕 Welcome to the Shipping Bot!\n\n"
        "Commands:\n"
        "/shipping - Create a random ship (24h cooldown)\n"
        "/reset - Vote to reset current ship\n"
        "/status - Check current ship and cooldown\n"
        "/top - View top shippers and shipped users\n\n"
        "I'll track the last 500 users who message in this chat!"
    )

async def shipping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /shipping command"""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # Check if it's a group chat
    if update.effective_chat.type == 'private':
        await update.message.reply_text("❌ This command only works in group chats!")
        return
    
    can_ship, message = await bot_data.can_ship(chat_id, context)
    
    if not can_ship:
        await update.message.reply_text(message)
        return
    
    user1_id, user2_id = bot_data.create_ship(chat_id, user_id)
    
    # Get user information
    try:
        user1 = await context.bot.get_chat_member(chat_id, user1_id)
        user2 = await context.bot.get_chat_member(chat_id, user2_id)
        shipping_data = bot_data.get_shipping_data(chat_id)
        compatibility = shipping_data.get('compatibility', -1)
        compatibility_emoji = shipping_data.get('compatibility_emoji', '😑')
        # Get full name (first name + last name if available)
        user1_name = user1.user.first_name
        if user1.user.last_name:
            user1_name += f" {user1.user.last_name}"
        
        user2_name = user2.user.first_name
        if user2.user.last_name:
            user2_name += f" {user2.user.last_name}"
        
        # Create mentions with names (this will ping them)
        user1_mention = f'<a href="tg://user?id={user1_id}">{user1_name}</a>'
        user2_mention = f'<a href="tg://user?id={user2_id}">{user2_name}</a>'
        
        await update.message.reply_text(
            f"💘 NEW SHIP ALERT! 💘\n\n"
            f"{user1_mention} ❤️ {user2_mention}\n💪Ship Strength: {compatibility_emoji}{compatibility}%\n\n"
            f"🔒 Next shipping available in 24 hours!",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Error getting user info: {e}")
        # Fallback to user IDs
        await update.message.reply_text(
            f"💘 NEW SHIP ALERT! 💘\n\n"
            f"User {user1_id} ❤️ User {user2_id}\n💪Ship Strength: {compatibility_emoji}{compatibility}%\n\n"
            f"🔒 Next shipping available in 24 hours!"
        )

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /reset command"""
    logger.info("Received reset command")
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if update.effective_chat.type == 'private':
        await update.message.reply_text("❌ This command only works in group chats!")
        return
    
    if chat_id not in bot_data.current_pairs:
        await update.message.reply_text("❌ No active ship to reset!")
        return
    
    current_pair = bot_data.current_pairs[chat_id]
    unique_users = bot_data.get_unique_users(chat_id)
    
    # Check if user is part of current pair
    if user_id in current_pair:
        bot_data.reset_ship(chat_id)
        await update.message.reply_text("✅ Ship has been reset by a ship member!")
        return
    
    # Add vote
    bot_data.reset_votes[chat_id].add(user_id)
    votes_needed = len(unique_users) // 2 + (1 if len(unique_users) % 2 == 1 else 0)
    current_votes = len(bot_data.reset_votes[chat_id])
    
    if current_votes >= votes_needed:
        bot_data.reset_ship(chat_id)
        await update.message.reply_text(
            f"✅ Ship has been reset by community vote! ({current_votes}/{votes_needed} votes)"
        )
    else:
        await update.message.reply_text(
            f"🗳️ Reset vote registered! ({current_votes}/{votes_needed} votes needed)"
        )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command"""
    chat_id = update.effective_chat.id
    
    if update.effective_chat.type == 'private':
        await update.message.reply_text("❌ This command only works in group chats!")
        return
    
    unique_users = bot_data.get_unique_users(chat_id)
    status_msg = f"📊 <b>Chat Status</b>\n\n"
    status_msg += f"👥 Active users: {len(unique_users)}\n\n"
    
    if chat_id in bot_data.current_pairs:
        user1_id, user2_id = bot_data.current_pairs[chat_id]
        shipping_data = bot_data.get_shipping_data(chat_id)
        compatibility = shipping_data.get('compatibility', -1)
        compatibility_emoji = shipping_data.get('compatibility_emoji', '😑')
        
        try:
            user1 = await context.bot.get_chat_member(chat_id, user1_id)
            user2 = await context.bot.get_chat_member(chat_id, user2_id)
            
            # Get full name (first name + last name if available)
            user1_name = user1.user.first_name
            if user1.user.last_name:
                user1_name += f" {user1.user.last_name}"
            
            user2_name = user2.user.first_name
            if user2.user.last_name:
                user2_name += f" {user2.user.last_name}"
            
            status_msg += f"💑 Current ship:\n"
            status_msg += f"{user1_name} ❤️ {user2_name}\n💪Ship Strength: {compatibility_emoji}{compatibility}%\n\n"
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            status_msg += f"💑 Current ship:\n"
            status_msg += f"User {user1_id} ❤️ User {user2_id}\n💪Ship Strength: {compatibility_emoji}{compatibility}%\n\n"
    
    if chat_id in bot_data.last_shipping:
        time_passed = datetime.now() - bot_data.last_shipping[chat_id]
        if time_passed < timedelta(hours=24):
            remaining = timedelta(hours=24) - time_passed
            hours = remaining.seconds // 3600
            minutes = (remaining.seconds % 3600) // 60
            status_msg += f"⏰ Next shipping in: {hours}h {minutes}m"
        else:
            status_msg += "✅ Shipping available!"
    else:
        status_msg += "✅ Shipping available!"
    
    await update.message.reply_text(status_msg, parse_mode='HTML')

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /top command - show top shippers and shipped users"""
    chat_id = update.effective_chat.id
    
    if update.effective_chat.type == 'private':
        await update.message.reply_text("❌ This command only works in group chats!")
        return
    
    top_msg = "🏆 <b>Shipping Leaderboards</b>\n\n"
    
    # Top Shippers (who pressed /shipping)
    shipper_stats = bot_data.shipper_stats[chat_id]
    if shipper_stats:
        sorted_shippers = sorted(shipper_stats.items(), key=lambda x: x[1], reverse=True)[:5]
        top_msg += "👑 <b>Top Shippers</b> (initiated ships):\n"
        
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for idx, (user_id, count) in enumerate(sorted_shippers):
            try:
                user = await context.bot.get_chat_member(chat_id, user_id)
                user_name = user.user.first_name
                if user.user.last_name:
                    user_name += f" {user.user.last_name}"
                
                top_msg += f"{medals[idx]} {user_name}: {count} ships\n"
            except Exception as e:
                logger.error(f"Error getting user info: {e}")
                top_msg += f"{medals[idx]} User {user_id}: {count} ships\n"
    else:
        top_msg += "👑 <b>Top Shippers</b>: No data yet\n"
    
    top_msg += "\n"
    
    # Top Shipped (who were in ships)
    shipped_stats = bot_data.shipped_stats[chat_id]
    if shipped_stats:
        sorted_shipped = sorted(shipped_stats.items(), key=lambda x: x[1], reverse=True)[:5]
        top_msg += "💕 <b>Most Shipped</b> (in ships):\n"
        
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for idx, (user_id, count) in enumerate(sorted_shipped):
            try:
                user = await context.bot.get_chat_member(chat_id, user_id)
                user_name = user.user.first_name
                if user.user.last_name:
                    user_name += f" {user.user.last_name}"
                
                top_msg += f"{medals[idx]} {user_name}: {count} times\n"
            except Exception as e:
                logger.error(f"Error getting user info: {e}")
                top_msg += f"{medals[idx]} User {user_id}: {count} times\n"
    else:
        top_msg += "💕 <b>Most Shipped</b>: No data yet\n"
    
    await update.message.reply_text(top_msg, parse_mode='HTML')

async def track_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Track users who send messages"""
    logger.info('Message received')
    if update.effective_chat.type != 'private' and update.effective_user:
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        # Don't track bots
        if not update.effective_user.is_bot:
            bot_data.add_user(chat_id, user_id)

async def post_init(application: Application):
    """Set bot commands after initialization"""
    await application.bot.set_my_commands([
        ("shipping", "Create a random ship (24h cooldown)"),
        ("reset", "Vote to reset the current ship"),
        ("status", "Check current ship and cooldown"),
        ("top", "View top shippers and shipped users"),
        ("start", "Show bot information"),
    ])

def main():
    """Start the bot"""
    # Replace with your bot token
    
    TOKEN = os.environ['TG_TOKEN']  # Don't share your token!
    
    # Create application
    application = Application.builder().token(TOKEN).build()
    application.post_init = post_init
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("shipping", shipping))
    application.add_handler(CommandHandler("reset", reset))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("top", top))
    
    # Track all messages
    application.add_handler(MessageHandler(
        filters.ALL, 
        track_messages
    ))
    
    # Start bot
    logger.info("Bot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()