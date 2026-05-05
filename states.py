from aiogram.fsm.state import State, StatesGroup


class MenuStates(StatesGroup):
    idle = State()


class DealCreationStates(StatesGroup):
    waiting_type = State()
    waiting_product_name = State()
    waiting_payment_method = State()
    waiting_price = State()
    waiting_currency = State()


class CardStates(StatesGroup):
    waiting_card_details = State()


class AdminStates(StatesGroup):
    waiting_user_id = State()
    waiting_deal_id = State()


class JoinDealStates(StatesGroup):
    waiting_payment = State()


class GiftTransferStates(StatesGroup):
    waiting_gift = State()


class GiftDisputeStates(StatesGroup):
    waiting_dispute_proof = State()
    waiting_seller_response = State()


class ProductDisputeStates(StatesGroup):
    waiting_dispute_proof = State()
