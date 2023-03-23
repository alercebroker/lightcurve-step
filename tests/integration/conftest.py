import os
import pytest
from confluent_kafka.admin import AdminClient, NewTopic
from apf.producers import KafkaProducer
import uuid
from fastavro.utils import generate_many
from fastavro.schema import load_schema


@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig):
    return os.path.join(
        str(pytestconfig.rootdir), "tests/integration", "docker-compose.yaml"
    )


@pytest.fixture(scope="session")
def docker_compose_command():
    v2 = False
    if os.getenv("COMPOSE", "v1") == "v2":
        v2 = True
    return "docker compose" if v2 else "docker-compose"


def is_responsive_kafka(url):
    client = AdminClient({"bootstrap.servers": url})
    topics = ["test_topic"]
    new_topics = [NewTopic(topic, num_partitions=1) for topic in topics]
    fs = client.create_topics(new_topics)
    for topic, f in fs.items():
        try:
            f.result()
        except Exception as e:
            print(f"Can't create topic {topic}")
            print(e)
            return False
    produce_messages("correction")
    return True


@pytest.fixture(scope="session")
def kafka_service(docker_ip, docker_services):
    """Ensure that Kafka service is up and responsive."""
    port = docker_services.port_for("kafka", 9092)
    server = "{}:{}".format(docker_ip, port)
    docker_services.wait_until_responsive(
        timeout=30.0, pause=0.1, check=lambda: is_responsive_kafka(server)
    )
    return server


@pytest.fixture
def env_variables():
    random_string = uuid.uuid4().hex
    env_variables_dict = {
        "CONSUMER_SERVER": "localhost:9092",
        "CONSUMER_TOPICS": "correction",
        "CONSUMER_GROUP_ID": random_string,
        "METRICS_SERVER": "localhost:9092",
        "PRODUCER_SERVER": "localhost:9092",
        "PRODUCER_TOPIC": "lightcurve",
        "ENABLE_PARTITION_EOF": "True",
    }
    for key in env_variables_dict:
        os.environ[key] = env_variables_dict[key]

    return env_variables_dict


def produce_messages(topic):
    schema = load_schema("tests/integration/input_schema.avsc")
    producer = KafkaProducer(
        {
            "PARAMS": {"bootstrap.servers": "localhost:9092"},
            "TOPIC": topic,
            "SCHEMA": schema,
        }
    )
    messages = generate_many(schema, 10)
    producer.set_key_field("aid")

    for message in messages:
        producer.produce(message)
