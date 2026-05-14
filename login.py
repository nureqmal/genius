import streamlit as st
from utils.auth import sign_in, sign_up


def show():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("# 🔬 ResearchAI")
        st.markdown("##### AI-powered academic research platform")
        st.markdown("---")

        tab_login, tab_register = st.tabs(["Sign In", "Create Account"])

        with tab_login:
            st.markdown("<br>", unsafe_allow_html=True)
            email = st.text_input("Email", key="login_email", placeholder="you@university.edu")
            password = st.text_input("Password", type="password", key="login_password")
            st.markdown("<br>", unsafe_allow_html=True)

            if st.button("Sign In", use_container_width=True, type="primary", key="signin_btn"):
                if not email or not password:
                    st.warning("Please fill in all fields.")
                else:
                    with st.spinner("Signing in..."):
                        user, session, error = sign_in(email, password)
                    if error:
                        st.error(f"Login failed: {error}")
                    else:
                        st.session_state["user"] = user
                        st.session_state["session"] = session
                        st.success("Welcome back!")
                        st.rerun()

        with tab_register:
            st.markdown("<br>", unsafe_allow_html=True)
            reg_email = st.text_input("Email", key="reg_email", placeholder="you@university.edu")
            reg_password = st.text_input("Password", type="password", key="reg_password",
                                         help="Minimum 6 characters")
            reg_confirm = st.text_input("Confirm Password", type="password", key="reg_confirm")
            st.markdown("<br>", unsafe_allow_html=True)

            if st.button("Create Account", use_container_width=True, type="primary", key="register_btn"):
                if not reg_email or not reg_password:
                    st.warning("Please fill in all fields.")
                elif reg_password != reg_confirm:
                    st.error("Passwords do not match.")
                elif len(reg_password) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    with st.spinner("Creating account..."):
                        user, error = sign_up(reg_email, reg_password)
                    if error:
                        st.error(f"Registration failed: {error}")
                    else:
                        st.success("Account created! Please check your email to verify, then sign in.")
