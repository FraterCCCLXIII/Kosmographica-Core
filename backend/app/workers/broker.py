import dramatiq
from dramatiq.brokers.rabbitmq import RabbitmqBroker

from app.config import get_settings

settings = get_settings()
broker = RabbitmqBroker(url=settings.rabbitmq_url)
dramatiq.set_broker(broker)
