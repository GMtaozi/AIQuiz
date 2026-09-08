"""Email Service - 邮件通知服务

提供 SMTP 邮件发送能力，供通知系统在创建重要通知时同步发送邮件提醒。
设计原则：
- 配置驱动：smtp_enabled=false 时直接跳过，不发邮件
- 容错优先：邮件发送失败不影响主流程（日志记录后降级）
- 类型过滤：仅 warning/error/audit 类型发送邮件，info/success 不发送
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

# 需要发送邮件通知的类型（info/success 不打扰用户）
EMAIL_NOTIFICATION_TYPES = frozenset({"warning", "error", "audit"})


def send_email_notification(
    user_email: str,
    title: str,
    content: str,
    notification_type: str = "info",
) -> bool:
    """发送邮件通知

    Args:
        user_email: 收件人邮箱
        title: 邮件标题
        content: 邮件正文
        notification_type: 通知类型（决定是否需要发送邮件）

    Returns:
        bool: 发送成功返回 True，跳过或失败返回 False
    """
    # 类型过滤：非重要类型不发送邮件
    if notification_type not in EMAIL_NOTIFICATION_TYPES:
        return False

    # 配置检查：未启用 SMTP 或未配置邮箱时跳过
    if not getattr(settings, "smtp_enabled", False):
        logger.debug(f"SMTP 未启用，跳过邮件通知: {title}")
        return False

    smtp_host = getattr(settings, "smtp_host", "")
    smtp_port = getattr(settings, "smtp_port", 587)
    smtp_user = getattr(settings, "smtp_user", "")
    smtp_password = getattr(settings, "smtp_password", "")
    smtp_from = getattr(settings, "smtp_from", smtp_user)

    if not all([smtp_host, smtp_user, smtp_password]):
        logger.warning(f"SMTP 配置不完整，跳过邮件通知: host={smtp_host}, user={smtp_user}")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[智题AIQuiz] {title}"
        msg["From"] = smtp_from
        msg["To"] = user_email

        # 纯文本版本
        text_part = MIMEText(content, "plain", "utf-8")
        msg.attach(text_part)

        # HTML 版本
        html_content = f"""
        <html>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; border: 1px solid #e8e8e8; border-radius: 8px; overflow: hidden;">
                <div style="background: linear-gradient(135deg, #165DFF 0%, #4080FF 100%); padding: 20px; color: white;">
                    <h2 style="margin: 0; font-size: 18px;">智题 AIQuiz 通知</h2>
                </div>
                <div style="padding: 24px;">
                    <h3 style="margin-top: 0; color: #303133;">{title}</h3>
                    <p style="color: #606266; line-height: 1.6;">{content}</p>
                    <hr style="border: none; border-top: 1px solid #ebeef5; margin: 20px 0;" />
                    <p style="color: #909399; font-size: 12px; margin: 0;">
                        此邮件由系统自动发送，请勿直接回复。<br />
                        登录系统查看详细信息。
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        html_part = MIMEText(html_content, "html", "utf-8")
        msg.attach(html_part)

        # 发送邮件
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from, [user_email], msg.as_string())

        logger.info(f"邮件通知发送成功: {user_email}, title={title}")
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error(f"SMTP 认证失败，请检查用户名和密码: {smtp_user}")
        return False
    except smtplib.SMTPConnectError:
        logger.error(f"SMTP 连接失败: {smtp_host}:{smtp_port}")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP 发送失败: {e}")
        return False
    except Exception as e:
        logger.error(f"邮件发送异常: {e}", exc_info=True)
        return False


def should_send_email(notification_type: str) -> bool:
    """判断是否需要发送邮件通知

    Args:
        notification_type: 通知类型

    Returns:
        bool: 需要发送邮件返回 True
    """
    if notification_type not in EMAIL_NOTIFICATION_TYPES:
        return False
    if not getattr(settings, "smtp_enabled", False):
        return False
    return True
