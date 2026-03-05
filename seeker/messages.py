import streamlit as st
from shared.db import get_inbox, get_conversation, send_message, mark_messages_read, get_user_by_id


def show_seeker_messages(user: dict):
    st.markdown("## 💬 Messages")
    st.markdown("---")

    inbox = get_inbox(user['id'])

    if not inbox:
        st.info("No messages yet. You'll receive messages from providers about your applications.")
        return

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("### Conversations")
        for msg in inbox:
            other_name = msg.get('other_name', 'Unknown')
            job_title = msg.get('job_title', '')
            preview = msg.get('content', '')[:40] + '...' if len(msg.get('content', '')) > 40 else msg.get('content', '')
            other_id = msg['sender_id'] if msg['receiver_id'] == user['id'] else msg['receiver_id']

            if st.button(
                f"👤 **{other_name}**\n_{job_title}_\n{preview}",
                key=f"conv_{other_id}_{msg.get('job_id')}",
                use_container_width=True
            ):
                st.session_state['active_conv'] = {
                    'other_id': other_id,
                    'other_name': other_name,
                    'job_id': msg.get('job_id'),
                    'job_title': job_title
                }
                mark_messages_read(other_id, user['id'])
                st.rerun()

    with col2:
        conv = st.session_state.get('active_conv')
        if not conv:
            st.info("Select a conversation from the left.")
            return

        st.markdown(f"### {conv['other_name']} — {conv.get('job_title', '')}")
        messages = get_conversation(user['id'], conv['other_id'], conv.get('job_id'))

        chat_html = '<div style="height:400px;overflow-y:auto;padding:10px;background:#f9f9f9;border-radius:8px;">'
        for m in messages:
            is_me = m['sender_id'] == user['id']
            align = 'right' if is_me else 'left'
            bg = '#6366f1' if is_me else '#e5e7eb'
            color = 'white' if is_me else '#111'
            name = 'You' if is_me else m.get('sender_name', 'Them')
            chat_html += (
                f'<div style="text-align:{align};margin:8px 0;">'
                f'<small style="color:#888;">{name}</small><br>'
                f'<span style="background:{bg};color:{color};padding:8px 14px;'
                f'border-radius:18px;display:inline-block;max-width:75%;text-align:left;">'
                f'{m["content"]}</span>'
                f'<br><small style="color:#aaa;">{str(m.get("sent_at",""))[:16]}</small>'
                f'</div>'
            )
        chat_html += '</div>'
        st.markdown(chat_html, unsafe_allow_html=True)

        new_msg = st.text_input("Type a message...", key="seeker_msg_input", placeholder="Write your message here...")
        if st.button("Send 📤", type="primary") and new_msg.strip():
            send_message(user['id'], conv['other_id'], conv.get('job_id'), new_msg.strip())
            st.rerun()
