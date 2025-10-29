
import streamlit as st
import requests
import datetime
import pandas as pd
import re
from streamlit_chat import message

# --- Page and API Configuration ---
st.set_page_config(layout="wide", page_title="Dairy Manager")

API_URL = "http://127.0.0.1:8000"

st.title("Dairy Management System")
 
# --- Session State Initialization ---
if 'page' not in st.session_state:
    st.session_state.page = 'home'
if 'selected_customer_id' not in st.session_state:
    st.session_state.selected_customer_id = None
if 'show_log' not in st.session_state:
    st.session_state.show_log = False
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# --- Helper Functions ---
def parse_dates_from_command(command):
    dates = []
    date_pattern = r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})'
    range_match = re.search(r'from\s+' + date_pattern + r'\s+to\s+' + date_pattern, command)
    if range_match:
        start_day, start_month, start_year, end_day, end_month, end_year = map(int, range_match.groups())
        start_date = datetime.date(start_year, start_month, start_day)
        end_date = datetime.date(end_year, end_month, end_day)
        delta = end_date - start_date
        for i in range(delta.days + 1):
            day = start_date + datetime.timedelta(days=i)
            dates.append(day)
        return dates
    single_match = re.search(date_pattern, command)
    if single_match:
        day, month, year = map(int, single_match.groups())
        dates.append(datetime.date(year, month, day))
        return dates
    if "today" in command: dates.append(datetime.date.today())
    elif "yesterday" in command: dates.append(datetime.date.today() - datetime.timedelta(days=1))
    if not dates: dates.append(datetime.date.today())
    return dates

def get_customers():
    try:
        response = requests.get(f"{API_URL}/customers")
        if response.status_code == 200:
            return response.json()
    except requests.exceptions.ConnectionError:
        st.sidebar.error("Connection Error!")
        return []
    return []

# --- MODIFIED: Rewritten Global Assistant Logic ---
def process_global_chat_command(command):
    """Parses commands that can target any customer by name."""
    command = command.lower()
    customers = get_customers()
    customer_map = {c['name'].lower(): c for c in customers}

    # Intent 0: Add New Customer
    if "add new customer" in command:
        try:
            name_match = re.search(r'add new customer\s+([a-zA-Z0-9_]+)', command)
            if not name_match: return "Couldn't find a name. Use 'add new customer [name]...'"
            name = name_match.group(1).strip().title()

            morn_qty = 0.0
            eve_qty = 0.0

            # --- FIX WAS HERE ---
            # Split the command by 'and' to handle morning and evening parts separately and more robustly.
            parts = command.split(' and ')
            for part in parts:
                number_match = re.search(r'(\d+\.?\d*)', part)
                if number_match:
                    quantity = float(number_match.group(1))
                    # Check if this part of the command refers to morning or evening
                    if 'morning' in part:
                        morn_qty = quantity
                    # Use 'even' to catch both 'evening' and typos like 'evenign'
                    elif 'even' in part:
                        eve_qty = quantity
            # --- END FIX ---
            
            customer_data = {"name": name, "address": "", "phone_number": "", 
                             "default_milk_morning": morn_qty, "default_milk_evening": eve_qty}
            
            response = requests.post(f"{API_URL}/customers", json=customer_data)
            return f"✅ Success! Customer '{name}' added with {morn_qty}L morning and {eve_qty}L evening default milk." if response.status_code == 201 else f"❌ Error: {response.text}"
        except Exception as e: return f"An error occurred: {e}"

    # Find which customer is being talked about for all other intents
    target_customer = None
    for name, customer_data in customer_map.items():
        if name in command:
            target_customer = customer_data
            break
    
    if not target_customer:
        return "Please mention a valid customer's name in your request."

    customer_id = target_customer['_id']
    customer_name = target_customer['name']
    today = datetime.date.today()
    month, year = today.month, today.year

    # Intent 1: Log Variation
    if any(word in command for word in ["add", "log", "put", "set"]):
        try:
            quantity_match = re.search(r'(\d+\.?\d*)', command)
            if not quantity_match: return "Couldn't figure out the quantity."
            quantity = float(quantity_match.group(1))
            morn_qty, eve_qty = 0.0, 0.0
            if "morning" in command: morn_qty = quantity
            elif "evening" in command: eve_qty = quantity
            elif "both" in command: morn_qty = eve_qty = quantity
            else: return "Please specify morning or evening."
            
            dates_to_log = parse_dates_from_command(command)
            success_count = 0
            for log_date in dates_to_log:
                variation_data = {"customer_id": customer_id, "date": log_date.isoformat(), "morning_quantity": morn_qty, "evening_quantity": eve_qty}
                response = requests.post(f"{API_URL}/variations", json=variation_data)
                if response.status_code == 201: success_count += 1
            
            return f"✅ Success! Logged variation for '{customer_name}' for {success_count} day(s)."
        except Exception as e: return f"An error occurred: {e}"

    # Intent 2: Get Bill
    elif any(word in command for word in ["bill", "total", "summary", "due"]):
        sheet_response = requests.get(f"{API_URL}/customers/{customer_id}/monthly_sheet", params={"month": month, "year": year})
        if sheet_response.status_code == 200:
            totals = sheet_response.json().get("totals", {})
            amount_due = totals.get("amount_due", 0)
            return f"💰 The total bill for {customer_name} for {month}/{year} is ₹ {amount_due:.2f}."
        else: return "❌ Error fetching the bill."
    
    # Intent 3: Analyze Consumption Patterns
    elif any(word in command for word in ["extra", "more", "less", "skip", "didn't take", "not take"]):
        summary_response = requests.get(f"{API_URL}/customers/{customer_id}/variations_summary", params={"month": month, "year": year})
        if summary_response.status_code != 200: return "❌ Could not retrieve variation data."
        summary_data = summary_response.json()
        if not summary_data: return f"No variations were logged for {customer_name} this month."
        
        more_days, less_days, skipped_days = [], [], []
        
        for item in summary_data:
            if item['total'] == 0:
                skipped_days.append(f"On **{item['date']}**")
                continue 
            
            morning_diff = item['morning'] - target_customer['default_milk_morning']
            evening_diff = item['evening'] - target_customer['default_milk_evening']
            
            if morning_diff > 0 or evening_diff > 0:
                details = []
                if morning_diff > 0: details.append(f"{morning_diff:.2f}L extra in the morning")
                if evening_diff > 0: details.append(f"{evening_diff:.2f}L extra in the evening")
                more_days.append(f"On **{item['date']}**: took {', '.join(details)}.")

            if morning_diff < 0 or evening_diff < 0:
                details = []
                if morning_diff < 0: details.append(f"{abs(morning_diff):.2f}L less in the morning")
                if evening_diff < 0: details.append(f"{abs(evening_diff):.2f}L less in the evening")
                less_days.append(f"On **{item['date']}**: took {', '.join(details)}.")

        response_parts = []
        if any(w in command for w in ["extra", "more"]):
            if more_days: response_parts.append("Here are the days they took **more** milk:\n- " + "\n- ".join(more_days))
            else: response_parts.append("They did not take extra milk this month.")
                
        if any(w in command for w in ["less", "not take"]):
            if less_days: response_parts.append("Here are the days they took **less** milk:\n- " + "\n- ".join(less_days))
            else: response_parts.append("They did not take less than the default this month.")
                
        if any(w in command for w in ["skip", "didn't take"]):
            if skipped_days: response_parts.append("Here are the days they **skipped** delivery:\n- " + "\n- ".join(skipped_days))
            else: response_parts.append("They did not skip any deliveries this month.")
        
        return "\n\n".join(response_parts) if response_parts else "Please be more specific (ask about 'more', 'less', or 'skipped' days)."

    # Fallback
    else:
        return "Sorry, I can't do that yet. Please try rephrasing."

# --- Sidebar UI ---
st.sidebar.title("Actions")
if st.sidebar.button("➕ Add New Customer"):
    st.session_state.page = 'add_customer'
    st.session_state.selected_customer_id = None
    st.session_state.show_log = False 
    st.session_state.chat_history = []

st.sidebar.markdown("---")
st.sidebar.title("Navigation")
if st.sidebar.button("🤖 Assistant"):
    st.session_state.page = 'assistant'
    st.session_state.selected_customer_id = None

if st.sidebar.button("👥 All Customers"):
    st.session_state.page = 'all_customers_list'
    st.session_state.selected_customer_id = None

# --- Main Page Content ---

if st.session_state.page == 'home':
    pass

elif st.session_state.page == 'assistant':
    st.subheader("🤖 Assistant")
    for i, (query, response) in enumerate(st.session_state.chat_history):
        message(query, is_user=True, key=f"global_user_{i}")
        message(response, key=f"global_bot_{i}")
    with st.form("global_chat_form", clear_on_submit=True):
        user_input = st.text_input("Ask your assistant:", "")
        submitted = st.form_submit_button("Send")
        if submitted and user_input:
            bot_response = process_global_chat_command(user_input)
            st.session_state.chat_history.append((user_input, bot_response))
            if len(st.session_state.chat_history) > 10:
                st.session_state.chat_history = st.session_state.chat_history[-10:]
            st.rerun()

elif st.session_state.page == 'add_customer':
    st.header("Add a New Customer")
    with st.form("new_customer_form"):
        name = st.text_input("Name")
        address = st.text_input("Address")
        phone = st.text_input("Phone Number")
        default_morn = st.number_input("Default Morning Milk (Liters)", min_value=0.0, step=0.25, format="%.2f")
        default_eve = st.number_input("Default Evening Milk (Liters)", min_value=0.0, step=0.25, format="%.2f")
        if st.form_submit_button("Add Customer"):
            customer_data = {"name": name, "address": address, "phone_number": phone, "default_milk_morning": default_morn, "default_milk_evening": default_eve}
            response = requests.post(f"{API_URL}/customers", json=customer_data)
            if response.status_code == 201:
                st.success(f"Customer '{name}' added!")
                st.session_state.page = 'all_customers_list'
                st.rerun()
            else: st.error("Failed to add customer.")

elif st.session_state.page == 'all_customers_list':
    st.header("All Customers")
    customers = get_customers()
    if customers:
        cols = st.columns(4) 
        for i, cust in enumerate(customers):
            with cols[i % 4]:
                if st.button(cust['name'], key=cust['_id'], use_container_width=True):
                    st.session_state.page = 'view_customer'
                    st.session_state.selected_customer_id = cust['_id']
                    st.session_state.show_log = False
                    st.rerun()
    else: st.info("No customers found. Click 'Add New Customer' to get started.")

elif st.session_state.page == 'view_customer' and st.session_state.selected_customer_id:
    customers = get_customers() 
    selected_customer_details = next((cust for cust in customers if cust['_id'] == st.session_state.selected_customer_id), None)
    if selected_customer_details:
        st.header(f"Details for: {selected_customer_details['name']}")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"**Address:** {selected_customer_details['address']}")
            st.write(f"**Phone:** {selected_customer_details['phone_number']}")
        col2.metric("Default Morning Milk", f"{selected_customer_details['default_milk_morning']:.2f} L")
        col3.metric("Default Evening Milk", f"{selected_customer_details['default_milk_evening']:.2f} L")
        st.markdown("---")
        
        col_log, col_summary = st.columns(2)
        with col_log:
            st.subheader("Log a Daily Variation")
            with st.form("variation_form"):
                var_date = st.date_input("Date", datetime.date.today(), max_value=datetime.date.today())
                morn_qty = st.number_input("Morning Quantity (Liters)", min_value=0.0, step=0.25, format="%.2f")
                eve_qty = st.number_input("Evening Quantity (Liters)", min_value=0.0, step=0.25, format="%.2f")
                if st.form_submit_button("Log Variation"):
                    variation_data = {"customer_id": selected_customer_details['_id'], "date": var_date.isoformat(), "morning_quantity": morn_qty, "evening_quantity": eve_qty}
                    response = requests.post(f"{API_URL}/variations", json=variation_data)
                    if response.status_code == 201: st.success(f"Variation on {var_date} logged!")
                    else: st.error("Failed to log variation.")

        with col_summary:
            st.subheader("Monthly Summary")
            today = datetime.date.today()
            sheet_month = st.selectbox("Select Month for Sheet", range(1, 13), index=today.month - 1)
            sheet_year = st.number_input("Select Year for Sheet", value=today.year)
        
        with st.expander("View Variations"):
            summary_response = requests.get(f"{API_URL}/customers/{selected_customer_details['_id']}/variations_summary", params={"month": sheet_month, "year": sheet_year})
            if summary_response.status_code == 200:
                summary_data = summary_response.json()
                if not summary_data: st.write("No variations found for the selected month.")
                else:
                    for item in summary_data:
                        details = []
                        morn_change = item['morning'] - selected_customer_details['default_milk_morning']
                        if morn_change > 0: details.append(f"took {morn_change:.2f}L extra in morning")
                        elif morn_change < 0: details.append(f"took {abs(morn_change):.2f}L less in morning")
                        eve_change = item['evening'] - selected_customer_details['default_milk_evening']
                        if eve_change > 0: details.append(f"took {eve_change:.2f}L extra in evening")
                        elif eve_change < 0: details.append(f"took {abs(eve_change):.2f}L less in evening")
                        if item['total'] == 0: summary_line = f"**{item['date']}:** Skipped delivery"
                        else: summary_line = f"**{item['date']}:** {', '.join(details)}. (Total: {item['total']:.2f}L)"
                        st.write(summary_line)
        
        if st.button("View Full Monthly Milk Log"):
            st.session_state.show_log = not st.session_state.show_log

        if st.session_state.show_log:
            sheet_response = requests.get(f"{API_URL}/customers/{selected_customer_details['_id']}/monthly_sheet", params={"month": sheet_month, "year": sheet_year})
            if sheet_response.status_code == 200:
                response_data = sheet_response.json()
                sheet_data = response_data.get("sheet_data", [])
                totals = response_data.get("totals", {})
                if sheet_data:
                    df = pd.DataFrame(sheet_data)
                    total_row = pd.DataFrame([{"Date": "---", "Morning (L)": totals.get('total_morning'), "Evening (L)": totals.get('total_evening'), "Daily Total (L)": totals.get('grand_total_liters')}])
                    df = pd.concat([df, total_row], ignore_index=True)
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    st.metric(label=f"Total Bill for {sheet_month}/{sheet_year}", value=f"₹ {totals.get('amount_due', 0):.2f}")
                else: st.info("No data for the selected month.")
            else: st.error("Could not load monthly sheet data.")

else:
    st.session_state.page = 'home'
    st.rerun()