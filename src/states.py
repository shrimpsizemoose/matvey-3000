from aiogram.fsm.state import State, StatesGroup


class EditPicStates(StatesGroup):
    """States for the /edit_pic mask-based inpainting wizard."""
    waiting_for_original = State()  # Step 2: awaiting original image
    waiting_for_marked = State()    # Step 4: awaiting marked image
    waiting_for_prompt = State()    # Step 6: awaiting edit prompt
