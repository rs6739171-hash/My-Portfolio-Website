import openjarvis
import litellm

print(f"OpenJarvis: {getattr(openjarvis, '__version__', 'installed')}")
print(f"OpenJarvis package: {openjarvis.__file__}")
print(f"LiteLLM: {getattr(litellm, '__version__', 'installed')}")
