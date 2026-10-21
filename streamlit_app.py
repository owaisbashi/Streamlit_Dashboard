from pathlib import Path
from datetime import datetime
import base64
import contextlib
import importlib.util
import io
import re
import shutil
import subprocess
import sys
import pandas as pd	

import streamlit as st
import webbrowser



import webbrowser
import streamlit as st

if st.button("🎫 Launch Helix"):
    webbrowser.open_new_tab(
        "https://o2ukusm-smartit.onbmc.com/smartit/"
    )



BASE_DIR = Path(__file__).resolve().parent
SCRIPT_DIR = BASE_DIR / "scripts"

SHAREPOINT_FOLDER = Path(
    "/Users/Ovais.Bashir/OneDrive/SmartMeterTools"
)

TOOL_LINKS_FILE = SHAREPOINT_FOLDER / "tool_links.csv"
MESSAGE_CODES_FILE = SHAREPOINT_FOLDER / "message_codes.csv"

from attribute_comments import (
    ATTRIBUTE_COMMENTS,
    detect_alert,
    get_alert_name,
    get_attribute_definition,
    get_configured_attributes,
    get_configured_message_codes,
)

import csv



@st.cache_data
def load_message_codes():
    message_codes = {}
    

    csv_path = SHAREPOINT_FOLDER / "message_codes.csv"

    if not csv_path.exists():
        return message_codes

    with open(csv_path, newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        for row in reader:
            code = row.get("message_code", "").strip().upper()
            description = row.get("description", "").strip()

            if code:
                message_codes[code] = description

    return message_codes



# -----------------------------------------------------------------------------
# Locate and load the TOOL_Box Parses
# -----------------------------------------------------------------------------

def load_tool_links():

    if not TOOL_LINKS_FILE.exists():
        raise FileNotFoundError(
            f"tool_links.csv not found at: {TOOL_LINKS_FILE}"
        )

    df = pd.read_csv(
        TOOL_LINKS_FILE,
        encoding="utf-8-sig",
        dtype=str,
        keep_default_na=False
    )

    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
    )

    required_columns = {
        "icon",
        "name",
        "category",
        "description",
        "url"
    }

    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            "Missing columns: "
            + ", ".join(sorted(missing_columns))
        )

    for column in required_columns:
        df[column] = (
            df[column]
            .astype(str)
            .str.strip()
        )

    # A valid tool requires these three fields.
    df = df[
        (df["name"] != "")
        & (df["category"] != "")
        & (df["url"] != "")
    ].copy()

    return df
# Screen display
def render_toolbox():

    summary_file = SHAREPOINT_FOLDER / "Connections-Summary.txt"

    connections_file = SHAREPOINT_FOLDER / "Connections"


    if summary_file.exists():
        connections = summary_file.read_text(encoding="utf-8").strip()

    if connections_file.exists():

        full_text = connections_file.read_text(
            encoding="utf-8",
            errors="ignore"
        )

    col1, col2 = st.columns([1, 2])

    with col1:
        st.metric(
            "Total Connections (vEPG)",
            connections
        )

    with col2:
        st.text_area(
            "Latest Email",
            full_text,
            height=150,
            disabled=True
        )
        
# MME Dashboard
    image_file = SHAREPOINT_FOLDER / "MME_DASHBOARD_V3 - (Overview).png"


    @st.dialog("MME Dashboard", width="large")
    def show_dashboard():
        st.image(
        str(image_file),
            width="stretch"
        )


    top_left, top_right = st.columns([2, 1])

    with top_left:
        st.title("🔧 Smart Metering Toolbox")

    with top_right:
        if image_file.exists():
            st.image(
                str(image_file),
                width="stretch"
            )

            if st.button(
                "🔍 Enlarge",
                key="enlarge_mme",
                use_container_width=True
            ):
                show_dashboard()
        else:
            st.warning(f"Image not found: {image_file}")
        
    try:
        tool_links = pd.read_csv(
            TOOL_LINKS_FILE,
            encoding="utf-8-sig",
            dtype=str,
            keep_default_na=False
        )

    except Exception as error:
        st.error(f"Unable to load tool_links.csv: {error}")
        return

    # Clean column names
    tool_links.columns = (
        tool_links.columns
        .str.replace("\ufeff", "", regex=False)
        .str.strip()
        .str.lower()
    )

    required_columns = [
        "icon",
        "name",
        "category",
        "description",
        "url"
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in tool_links.columns
    ]

    if missing_columns:
        st.error(
            "Missing columns in tool_links.csv: "
            + ", ".join(missing_columns)
        )
        return

    # Clean values
    for column in required_columns:
        tool_links[column] = (
            tool_links[column]
            .astype(str)
            .str.strip()
        )

    # Keep valid rows
    tool_links = tool_links[
        (tool_links["name"] != "")
        & (tool_links["category"] != "")
    ].copy()

    if tool_links.empty:
        st.warning("No valid tools found in tool_links.csv")
        return

    # Get all categories
    categories = sorted(
        tool_links["category"].unique(),
        key=str.casefold
    )

    # Everything below must remain inside this loop
    for category in categories:

        category_tools = tool_links[
            tool_links["category"].str.casefold()
            == category.casefold()
        ].copy()

        category_tools = category_tools.sort_values(
            by="name",
            key=lambda values: values.str.casefold()
        )

        with st.expander(
            f"📁 {category}",
            expanded=False
        ):

         for _, row in category_tools.iterrows():

            icon = row["icon"] or "🔗"
            name = row["name"]
            description = row["description"]
            url = row["url"]

            if url:
                st.link_button(
                    f"{icon} {name}",
                    url,
                    use_container_width=True
                )
            else:
                st.button(
                    f"{icon} {name}",
                    disabled=True,
                    use_container_width=True,
                    key=f"missing_{category}_{name}"
                )
                if description:
                    st.caption(description)

                st.write("")
   
# ---------------------------------------------------------------------------
# Locate and load the INCIDENT-Rota
# -----------------------------------------------------------------------------
def get_current_incident_owner():

    rota_file = SHAREPOINT_FOLDER / "Incident-Rota.csv"

    rota = pd.read_csv(
        rota_file,
        encoding="utf-8-sig"
    )

    current_week = datetime.now().isocalendar().week

    current_row = rota[
        rota["Week"] == current_week
    ]

    if current_row.empty:
        return None

    return current_row.iloc[0]
# -----------------------------------------------------------------------------
# Locate and load the DMM parser
# -----------------------------------------------------------------------------
def find_dmm_script():
    """Find DMM_Kun_v53.py beside app.py or inside the scripts folder."""
    candidates = [
        BASE_DIR / "DMM_Kun_v53.py",
        SCRIPT_DIR / "DMM_Kun_v53.py",
    ]
    return next((path for path in candidates if path.exists()), candidates[0])


DMM_PATH = find_dmm_script()


def load_module(file_path, module_name):
    """Load a Python file without executing its command-line main function."""
    file_path = Path(file_path)
    module_folder = str(file_path.parent)

    # This lets DMM_Kun_v53.py find inttypes.py and obis_dlms_conversion.py.
    if module_folder not in sys.path:
        sys.path.insert(0, module_folder)

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load {file_path.name}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@st.cache_resource
def load_dmm_module(file_path_string):
    """Load the DMM module once and reuse it across Streamlit reruns."""
    return load_module(Path(file_path_string), "dmm_kun_streamlit")


# -----------------------------------------------------------------------------
# DMM input and parsing helpers
# -----------------------------------------------------------------------------
def normalise_message(value, input_format):
    """Convert Base64 input to hex, or validate hexadecimal input."""
    value = "".join(value.split())

    if not value:
        raise ValueError("Enter a message before selecting Parse.")

    if input_format == "Base64 (b64)":
        try:
            return base64.b64decode(value, validate=True).hex().upper()
        except Exception as exc:
            raise ValueError("The value is not valid Base64.") from exc

    try:
        bytes.fromhex(value)
    except ValueError as exc:
        raise ValueError(
            "The value is not valid hexadecimal. Use characters 0-9 and A-F."
        ) from exc

    return value.upper()


def parse_dmm_message(module, value, input_format):
    """Parse one message and return output, payload hex, and message code."""
    message = normalise_message(value, input_format)
    parser = module.DMMMessage()

    # DMM_Kun_v53.py writes its result with print(), so capture stdout.
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        print(module.VERSION)
        print()
        print(message)
        print()

        if module.PARSE_MESSAGE:
            parser.parseMessage(message)

    payload_hex = "".join(parser.payload or [])
    message_code = "".join(parser.messageCode or []).upper()

    return output.getvalue(), payload_hex, message_code



def normalise_code(value):
    return str(value or "").strip().upper().removeprefix("0X")


def payload_contains_alert(payload_hex, alert_code):
    compact = re.sub(r"[^0-9A-Fa-f]", "", payload_hex or "").upper()
    return normalise_code(alert_code) in compact
    
def extract_attribute_value(parsed_output, attribute_number):

    pattern = (
        rf"(?im)^Attribute\s+{attribute_number}"
        rf"\s*\([^)]*\)\s*:\s*([0-9A-Fa-f]+)"
    )

    match = re.search(pattern, str(parsed_output))

    if not match:
        return None, None

    raw_value = match.group(1)

    if raw_value.isdigit():
        decoded_value = int(raw_value, 10)
    else:
        decoded_value = int(raw_value, 16)

    return raw_value, decoded_value

def render_attribute_comment(
    alert_code,
    message_code,
    attribute_number,
    raw_value=None,
    decoded_value=None,
    key_suffix="",
):
    """
    Display a comments button for one configured attribute.
    """
    lookup_key = (
        normalise_code(alert_code),
        normalise_code(message_code),
        int(attribute_number),
    )

    definition = get_attribute_definition(
    alert_code=alert_code,
    message_code=message_code,
    attribute_number=attribute_number,
	)

    if not definition:
        return

    attribute_name = definition.get(
        "name",
        f"attribute_{attribute_number}",
    )

    description = definition.get(
        "description",
        "No attribute description has been provided.",
    )

    values = definition.get("values", {})

    state_key = (
        f"comment_"
        f"{lookup_key[0]}_"
        f"{lookup_key[1]}_"
        f"{attribute_number}_"
        f"{key_suffix}"
    )

    if raw_value is not None:
        button_label = (
            f"💬 Attribute {attribute_number}: "
            f"{attribute_name} = {raw_value}"
        )
    else:
        button_label = (
            f"💬 Attribute {attribute_number}: "
            f"{attribute_name} - not found"
        )

    if st.button(
        button_label,
        key=f"button_{state_key}",
    ):
        st.session_state[state_key] = not st.session_state.get(
            state_key,
            False,
        )

    if not st.session_state.get(state_key, False):
        return

    st.markdown(
        f"#### Attribute {attribute_number}: `{attribute_name}`"
    )

    st.write(description)

    value_col, parsed_col = st.columns(2)

    value_col.metric(
        "Value before parsing",
        raw_value if raw_value is not None else "Not found",
    )

    parsed_col.metric(
        "Value after parsing",
        (
            str(decoded_value)
            if decoded_value is not None
            else "Not found"
        ),
    )

    selected_value = decoded_value

    if selected_value not in values:
        if not values:
            st.warning(
                "No value definitions have been configured "
                "for this attribute."
            )
            return

        st.warning(
            "The value was not identified automatically. "
            "Select it below."
        )

        selected_value = st.selectbox(
            f"Attribute {attribute_number} value",
            options=sorted(values),
            format_func=lambda number: f"{number:02d}",
            key=f"value_{state_key}",
        )

    else:
        st.code(
            f"Attribute {attribute_number} "
            f"({attribute_number}) : "
            f"{raw_value} -> {decoded_value}",
            language="text",
        )

        st.success(
            f"Detected Attribute {attribute_number} "
            f"value: {decoded_value:02d}"
        )

    st.info(values[selected_value])
    


def get_message_description(message_code):
    message_codes = load_message_codes()

    return message_codes.get(
        str(message_code).strip().upper(),
        None,
    )
def show_message_code_preview():
    """
    Display a small sample of message codes loaded from message_codes.csv.
    """
    message_codes = load_message_codes()

    with st.sidebar.expander("Message code CSV preview"):
        if not message_codes:
            st.warning(
                "No message codes were loaded from message_codes.csv."
            )
            st.caption(
                f"Expected file: {BASE_DIR / 'message_codes.csv'}"
            )
            return

        st.success(
            f"{len(message_codes)} message codes loaded."
        )

        # Display the first 10 codes.
        for code, description in list(
            message_codes.items()
        )[:10]:
            st.markdown(
                f"**{code}**: {description}"
            )

# -----------------------------------------------------------------------------
# ASN.1 helpers
# -----------------------------------------------------------------------------
def decode_0012_integer(value):
    """Return the Message Code 0012 meaning for an ASN.1 INTEGER value."""
    mapping = {
        0: "success",
        1: "noImageHeld",
        2: "hashMismatch",
        3: "activationFailure",
    }
    return mapping.get(value)


def annotate_0012_asn1(asn1_output):
    """Add Message Code 0012 meanings beside recognised INTEGER values."""

    def replace_integer(match):
        displayed_value = match.group(1)

        # OpenSSL commonly displays ASN.1 INTEGER content in hexadecimal.
        # Values 0 to 3 are identical in decimal and hexadecimal.
        try:
            numeric_value = int(displayed_value, 16)
        except ValueError:
            return match.group(0)

        meaning = decode_0012_integer(numeric_value)
        if meaning is None:
            return match.group(0)

        return f"{match.group(0)} ({meaning})"

    return re.sub(
        r"INTEGER\s*:([0-9A-Fa-f]+)",
        replace_integer,
        asn1_output,
    )


def asn1_parse_payload(payload_hex):
    """
    Decode the hexadecimal payload and pass its DER bytes to OpenSSL.

    This is equivalent to:
    echo '<payload>' | xxd -r -p | openssl asn1parse -inform DER -i
    """
    if not payload_hex:
        return False, "No payload was extracted from the DMM message."

    if shutil.which("openssl") is None:
        return False, "OpenSSL was not found on this computer or is not on PATH."

    try:
        der_bytes = bytes.fromhex(payload_hex)
    except ValueError as exc:
        return False, f"The extracted payload is not valid hexadecimal: {exc}"

    try:
        result = subprocess.run(
            ["openssl", "asn1parse", "-inform", "DER", "-i"],
            input=der_bytes,
            capture_output=True,
            timeout=60,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "OpenSSL ASN.1 parsing exceeded the 60-second limit."
    except Exception as exc:
        return False, f"Could not run OpenSSL: {exc}"

    stdout = result.stdout.decode("utf-8", errors="replace")
    stderr = result.stderr.decode("utf-8", errors="replace")

    if result.returncode != 0:
        return False, stderr or stdout or "OpenSSL could not parse the payload."

    return True, stdout


# -----------------------------------------------------------------------------
# DMM / GBCS Streamlit app
# -----------------------------------------------------------------------------
def render_dmm_parser():
    st.header("DMM / GBCS Message Parser")

    try:
        displayed_path = DMM_PATH.relative_to(BASE_DIR)
    except ValueError:
        displayed_path = DMM_PATH

    st.caption(f"Parser file: {displayed_path}")

    if not DMM_PATH.exists():
        st.error(
            "DMM_Kun_v53.py was not found. Put it beside app.py or inside "
            "the scripts folder."
        )
        return

    input_format = st.radio(
        "Input format",
        ["Base64 (b64)", "Hexadecimal (b16)"],
        horizontal=True,
    )

    input_method = st.radio(
        "Input method",
        ["Paste one message", "Upload a text file"],
        horizontal=True,
    )

    messages = []

    if input_method == "Paste one message":
        message = st.text_area(
            "Message",
            height=220,
            placeholder="Paste the Base64 or hexadecimal DMM/GBCS message here",
        )
        if message.strip():
            messages = [message]
    else:
        uploaded_file = st.file_uploader(
            "Upload a text file containing one message per line",
            type=["txt", "log", "csv"],
        )

        if uploaded_file is not None:
            text = uploaded_file.getvalue().decode("utf-8-sig")
            messages = [line.strip() for line in text.splitlines() if line.strip()]
            st.caption(f"Loaded {len(messages)} non-empty line(s).")

    if st.button("🔎 Parse DMM message", type="primary", disabled=not messages):
        try:
            module = load_dmm_module(str(DMM_PATH))
            results = []
            parsed_items = []

            for line_number, message in enumerate(messages, start=1):
                try:
                    parsed_output, payload_hex, message_code = parse_dmm_message(
                        module,
                        message,
                        input_format,
                    )
                    message_description = get_message_description(message_code)

                    if not message_description:
                        message_description = "Not available"

    
                    results.append(
                        f"{'=' * 60}\n"
                        f"Line {line_number}\n"
                        f"{'=' * 60}\n"
                        f"{parsed_output}"
                    )

                    parsed_items.append(
                        {
                            "line_number": line_number,
                            "payload_hex": payload_hex,
                            "message_code": message_code,
                            "message_description": message_description,
                            "parsed_output": parsed_output,
                        }
                    )

                except Exception as exc:
                    results.append(
                        f"{'=' * 60}\n"
                        f"Line {line_number}\n"
                        f"{'=' * 60}\n"
                        f"ERROR: {type(exc).__name__}: {exc}"
                    )

            st.session_state["dmm_output"] = "\n\n".join(results)
            st.session_state["parsed_items"] = parsed_items
            st.session_state.pop("asn1_output", None)
            st.session_state.pop("asn1_error", None)
            st.success("Parsing completed.")

        except ModuleNotFoundError as exc:
            st.error(
                f"Missing local module: {exc.name}. Keep inttypes.py and "
                "obis_dlms_conversion.py in the same folder as DMM_Kun_v53.py."
            )
        except Exception as exc:
            st.exception(exc)

    # Display the standard DMM parser result.
    if st.session_state.get("dmm_output"):
        st.subheader("Parsed output")
        st.code(st.session_state["dmm_output"], language="text")

        st.download_button(
            "⬇️ Download parsed output",
            data=st.session_state["dmm_output"],
            file_name="dmm_parsed_output.txt",
            mime="text/plain",
        )

    # Display and decode the payload extracted by DMM_Kun_v53.py.
    parsed_items = st.session_state.get("parsed_items", [])
    items_with_payload = [item for item in parsed_items if item["payload_hex"]]

    if items_with_payload:
        st.divider()
        st.subheader("ASN.1 payload decoder")

        selected_item = items_with_payload[0]
        if len(items_with_payload) > 1:
            selected_line = st.selectbox(
                "Select a parsed line",
                options=[item["line_number"] for item in items_with_payload],
                format_func=lambda number: f"Line {number}",
            )
            selected_item = next(
                item
                for item in items_with_payload
                if item["line_number"] == selected_line
            )

        payload_hex = selected_item["payload_hex"]
        message_code = selected_item["message_code"]
        message_description = selected_item.get("message_description")
        parsed_output = selected_item.get("parsed_output", "")
                
        st.write(
            f"**Message code:** "
            f"`{message_code or 'Not available'}`"
        )

        message_description = selected_item.get(
            "message_description",
            "Not available"
        )

        st.info(
            f"Message Description: {message_description}"
        )
        
        with st.expander("Show extracted payload hex"):
            st.code(payload_hex, language="text")

        # ---------------------------------------------------------
        # Dynamically display configured attribute comments
        # ---------------------------------------------------------
        configured_message_codes = get_configured_message_codes()
        normalised_message_code = normalise_code(message_code)

        if normalised_message_code in configured_message_codes:
            # Detect an alert associated with this message code.
            # Search the parsed output first, then the payload.
            alert_code = detect_alert(
                parsed_output,
                normalised_message_code,
            )

            if alert_code is None:
                alert_code = detect_alert(
                    payload_hex,
                    normalised_message_code,
                )

            # A wildcard definition can still work when an alert is not
            # configured for this message code.
            lookup_alert_code = alert_code or "*"

            configured_attributes = get_configured_attributes(
                alert_code=lookup_alert_code,
                message_code=normalised_message_code,
            )

            if configured_attributes:
                st.subheader("Attribute comments")

                if alert_code:
                    st.info(
                        f"Alert 0x{alert_code}: "
                        f"{get_alert_name(alert_code, normalised_message_code)}"
                    )
                else:
                    st.caption(
                        f"No recognised alert was detected for Message Code "
                        f"{normalised_message_code}. Using shared definitions."
                    )

                for attribute_number in configured_attributes:
                    raw_value, decoded_value = extract_attribute_value(
                        parsed_output,
                        attribute_number,
                    )

                    render_attribute_comment(
                        alert_code=lookup_alert_code,
                        message_code=normalised_message_code,
                        attribute_number=attribute_number,
                        raw_value=raw_value,
                        decoded_value=decoded_value,
                        key_suffix=(
                            f"{selected_item['line_number']}_"
                            f"{normalised_message_code}_"
                            f"{lookup_alert_code}_"
                            f"{attribute_number}"
                        ),
                    )

            else:
                st.caption(
                    "No attribute comments are configured for "
                    f"Message Code {normalised_message_code}"
                    + (
                        f", Alert 0x{alert_code}."
                        if alert_code
                        else "."
                    )
                )
        # ---------------------------------------------------------
        # ASN.1 decoder
        # ---------------------------------------------------------
        if st.button("🔐 ASN.1 Decode Payload"):
            with st.spinner(
                "Running OpenSSL ASN.1 parser..."
            ):
                success, result = asn1_parse_payload(
                    payload_hex
                )

            if success:
                # Message Code 0012 INTEGER meanings:
                # 0 = success
                # 1 = noImageHeld
                # 2 = hashMismatch
                # 3 = activationFailure
                if message_code == "0012":
                    result = annotate_0012_asn1(
                        result
                    )

                st.session_state["asn1_output"] = result
                st.session_state["asn1_error"] = None

            else:
                st.session_state["asn1_output"] = None
                st.session_state["asn1_error"] = result

        if st.session_state.get("asn1_output"):
            st.subheader("ASN.1 structure")

            if message_code == "0012":
                st.info(
                    "Message Code 0012 annotations: "
                    "0 = success, "
                    "1 = noImageHeld, "
                    "2 = hashMismatch, "
                    "3 = activationFailure."
                )

            st.code(
                st.session_state["asn1_output"],
                language="text",
            )

            st.download_button(
                "⬇️ Download ASN.1 output",
                data=st.session_state["asn1_output"],
                file_name="asn1_parsed_output.txt",
                mime="text/plain",
            )

        if st.session_state.get("asn1_error"):
            st.error(
                st.session_state["asn1_error"]
            )

# -----------------------------------------------------------------------------
# Generic command-line script launcher
# -----------------------------------------------------------------------------
def discover_scripts():
    """Find scripts, excluding the DMM parser handled by its own page."""
    if not SCRIPT_DIR.exists():
        return {}

    excluded = {"DMM_Kun_v53.py", "__init__.py"}

    return {
        file.stem.replace("_", " ").title(): file
        for file in sorted(SCRIPT_DIR.glob("*.py"))
        if file.name not in excluded
    }


def render_script_runner(scripts):
    st.header("Command-line Script Runner")

    if not scripts:
        st.warning("No other Python scripts were found in the scripts folder.")
        return

    selected_label = st.selectbox("Choose a script to run", list(scripts))
    script_path = scripts[selected_label]

    st.info(f"Target file: `{script_path.relative_to(BASE_DIR)}`")
    st.caption(
        "This runner captures terminal output. Scripts that use input() cannot "
        "prompt in the browser and should be converted to Streamlit controls."
    )

    if st.button("🚀 Run selected script", type="primary"):
        try:
            with st.spinner(f"Running '{selected_label}'..."):
                result = subprocess.run(
                    [sys.executable, str(script_path)],
                    cwd=str(script_path.parent),
                    capture_output=True,
                    text=True,
                    timeout=300,
                    check=False,
                )

            if result.returncode == 0:
                st.success("Execution completed successfully.")
            else:
                st.error(
                    f"Execution failed with return code {result.returncode}."
                )

            if result.stdout:
                st.subheader("Output")
                st.code(result.stdout, language="text")

            if result.stderr:
                st.subheader("Errors / logs")
                st.code(result.stderr, language="text")

        except subprocess.TimeoutExpired:
            st.error("The script exceeded the 300-second execution limit.")
        except Exception as exc:
            st.exception(exc)

# -----------------------------
# Sidebar - Incident Queue
# -----------------------------

try:

    rota_file = SHAREPOINT_FOLDER / "Incident-Rota.csv"

    rota = pd.read_csv(
        rota_file,
        encoding="utf-8-sig"
    )

    current_week = datetime.now().isocalendar().week

    current_row = rota[
        rota["Week"] == current_week
    ]

    if not current_row.empty:

        owner = current_row.iloc[0]

        st.sidebar.markdown("### 📅 Incident Queue")

        st.sidebar.success(
            f"{owner['Queue']}"
        )

        st.sidebar.caption(
            f"Week {owner['Week']}"
        )

        st.sidebar.caption(
            f"Start: {owner['Week Commencing']}"
        )

except Exception as e:

    st.sidebar.warning(
        f"Unable to load rota: {e}"
    )
with st.sidebar:

    st.info("""
    **Getting Started**

    1. Choose an application from the menu below.
    2. Use Smart Metering Toolbox for links and dashboards.
    3. Use DMM / GBCS Parser to decode messages.
    4. Click Helix to launch Smart IT.
    """)



# -----------------------------------------------------------------------------
# App navigation
# -----------------------------------------------------------------------------
scripts = discover_scripts()
app_options = [
    "Smart Metering Toolbox",
    "DMM / GBCS Message Parser",
]

if scripts:
    app_options.append(
        "Other Python Scripts"
    )

selected_app = st.sidebar.selectbox("Choose an app", app_options)

if selected_app == "Smart Metering Toolbox":
    render_toolbox()

elif selected_app == "DMM / GBCS Message Parser":
    render_dmm_parser()

else:
    render_script_runner(scripts)