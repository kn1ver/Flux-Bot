import aiosqlite
import uuid
import time
from config import DB_PATH


class Database:
    def __init__(self):
        self.db_path = DB_PATH

    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    full_name TEXT,
                    is_banned INTEGER DEFAULT 0,
                    is_admin INTEGER DEFAULT 0,
                    card_details TEXT,
                    referral_code TEXT UNIQUE,
                    referred_by INTEGER,
                    created_at INTEGER NOT NULL
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS deals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    deal_id TEXT UNIQUE NOT NULL,
                    seller_id INTEGER NOT NULL,
                    buyer_id INTEGER,
                    deal_type TEXT NOT NULL,
                    product_name TEXT NOT NULL,
                    price_stars INTEGER NOT NULL,
                    price_currency REAL,
                    currency_type TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    payment_method TEXT,
                    gift_payload TEXT,
                    gift_message TEXT,
                    buyer_paid INTEGER DEFAULT 0,
                    seller_paid_gift INTEGER DEFAULT 0,
                    seller_card TEXT,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    referrer_id INTEGER NOT NULL,
                    referred_id INTEGER NOT NULL,
                    deal_id INTEGER,
                    commission_earned INTEGER DEFAULT 0,
                    created_at INTEGER NOT NULL
                )
            """)

            await db.commit()

    async def get_user(self, telegram_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def create_user(
        self, telegram_id: int, username: str = None, full_name: str = None
    ):
        async with aiosqlite.connect(self.db_path) as db:
            referral_code = str(uuid.uuid4())[:8]
            await db.execute(
                """INSERT OR IGNORE INTO users 
                (telegram_id, username, full_name, referral_code, created_at) 
                VALUES (?, ?, ?, ?, ?)""",
                (telegram_id, username, full_name, referral_code, int(time.time())),
            )
            await db.commit()

    async def update_user_card(self, telegram_id: int, card_details: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET card_details = ? WHERE telegram_id = ?",
                (card_details, telegram_id),
            )
            await db.commit()

    async def ban_user(self, telegram_id: int, ban: bool = True):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET is_banned = ? WHERE telegram_id = ?",
                (1 if ban else 0, telegram_id),
            )
            await db.commit()

    async def create_deal(
        self,
        seller_id: int,
        deal_type: str,
        product_name: str,
        price_stars: int,
        payment_method: str,
        price_currency: float = None,
        currency_type: str = None,
    ):
        deal_id = str(uuid.uuid4())[:8]
        now = int(time.time())

        seller = await self.get_user(seller_id)
        seller_card = seller.get("card_details") if seller else None

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO deals 
                (deal_id, seller_id, deal_type, product_name, price_stars, 
                 price_currency, currency_type, payment_method, status, seller_card, created_at, updated_at) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)""",
                (
                    deal_id,
                    seller_id,
                    deal_type,
                    product_name,
                    price_stars,
                    price_currency,
                    currency_type,
                    payment_method,
                    seller_card,
                    now,
                    now,
                ),
            )
            await db.commit()

        return await self.get_deal_by_deal_id(deal_id)

    async def get_deal_by_deal_id(self, deal_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM deals WHERE deal_id = ?", (deal_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_deal_by_id(self, deal_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM deals WHERE id = ?", (deal_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def join_deal(self, deal_id: int, buyer_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE deals SET buyer_id = ?, status = 'joined', updated_at = ? WHERE id = ?",
                (buyer_id, int(time.time()), deal_id),
            )
            await db.commit()

    async def update_deal_status(self, deal_id: int, status: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE deals SET status = ?, updated_at = ? WHERE id = ?",
                (status, int(time.time()), deal_id),
            )
            await db.commit()

    async def set_gift_info(
        self, deal_id: int, gift_payload: str, gift_message: str = None
    ):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE deals SET gift_payload = ?, gift_message = ? WHERE id = ?",
                (gift_payload, gift_message, deal_id),
            )
            await db.commit()

    async def get_user_deals(self, telegram_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT * FROM deals WHERE seller_id = ? OR buyer_id = ? 
                ORDER BY created_at DESC""",
                (telegram_id, telegram_id),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_all_deals(self, limit: int = 50, offset: int = 0):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM deals ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_user_deals_by_telegram_id(self, telegram_id: int, limit: int = 50):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT * FROM deals WHERE seller_id = ? OR buyer_id = ? 
                ORDER BY created_at DESC LIMIT ?""",
                (telegram_id, telegram_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def add_referral(
        self, referrer_id: int, referred_id: int, deal_id: int, commission: int
    ):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO referrals 
                (referrer_id, referred_id, deal_id, commission_earned, created_at) 
                VALUES (?, ?, ?, ?, ?)""",
                (referrer_id, referred_id, deal_id, commission, int(time.time())),
            )
            await db.commit()

    async def get_referral_stats(self, telegram_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT SUM(commission_earned) as total, COUNT(*) as count 
                FROM referrals WHERE referrer_id = ?""",
                (telegram_id,),
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else {"total": 0, "count": 0}

    async def is_user_referred(self, telegram_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT referred_by FROM users WHERE telegram_id = ?", (telegram_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

    async def mark_buyer_paid(self, deal_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE deals SET buyer_paid = 1, updated_at = ? WHERE id = ?",
                (int(time.time()), deal_id),
            )
            await db.commit()

    async def mark_seller_gift_paid(self, deal_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE deals SET seller_paid_gift = 1, updated_at = ? WHERE id = ?",
                (int(time.time()), deal_id),
            )
            await db.commit()

    async def gift_received_waiting_confirm(
        self, deal_id: int, gift_payload: str, gift_message: str = None
    ):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """UPDATE deals SET seller_paid_gift = 1, gift_payload = ?, gift_message = ?, 
                status = 'gift_received', updated_at = ? WHERE id = ?""",
                (gift_payload, gift_message, int(time.time()), deal_id),
            )
            await db.commit()

    async def get_old_incomplete_deals(self, hours: int = 24):
        cutoff_time = int(time.time()) - (hours * 3600)
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM deals WHERE status IN ('pending', 'joined') AND created_at < ?",
                (cutoff_time,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def delete_deal(self, deal_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM deals WHERE id = ?", (deal_id,))
            await db.commit()

    async def get_active_gift_deals_for_seller(self, seller_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT * FROM deals 
                WHERE seller_id = ? AND deal_type = 'gift' 
                AND buyer_paid = 1 AND seller_paid_gift = 0 
                AND status IN ('joined', 'paid')""",
                (seller_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]


db = Database()
