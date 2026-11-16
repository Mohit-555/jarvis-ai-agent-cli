class LlavaVision:
    def __init__(self):
        self.available = False

    def describe(self, image):
        return "Vision model requires a GPU. Not available on current hardware."
