"""
  For template payload management
"""

from org.yaml.snakeyaml.resolver import Resolver
from org.yaml.snakeyaml.nodes import Tag



class CustomResolver(Resolver):

    def addImplicitResolvers(self):
        
        self.addImplicitResolver(Tag.BOOL, self.BOOL, "yYnNtTfFoO")
        self.addImplicitResolver(Tag.MERGE, self.MERGE, "<")
        self.addImplicitResolver(Tag.NULL, self.NULL, "~nN\0")
        self.addImplicitResolver(Tag.NULL, self.EMPTY, None)
        self.addImplicitResolver(Tag.TIMESTAMP, self.TIMESTAMP, "0123456789");
        self.addImplicitResolver(Tag.VALUE, self.VALUE, "=")

    
