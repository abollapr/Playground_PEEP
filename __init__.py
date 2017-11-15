import playground
from .server import Serverfactory
from .client import Clientfactory

lab2Connector = playground.Connector(protocolStack=(Clientfactory, Serverfactory))
playground.setConnector("lab2_protocol", lab2Connector)
