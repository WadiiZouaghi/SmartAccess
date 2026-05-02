import cv2
import numpy as np
import hashlib

class WatermarkService:
    def __init__(self, block_size=8):
        self.block_size = block_size
        # Coefficients to modify (mid-frequency for robustness)
        self.coeff1 = (4, 4)
        self.coeff2 = (5, 5)

    def generate_hash(self, text):
        """Generates a SHA-256 hash of the log text."""
        return hashlib.sha256(text.encode()).hexdigest()

    def _text_to_bits(self, text):
        """Convert text to a list of bits."""
        bits = []
        for char in text:
            bin_char = bin(ord(char)).lstrip('0b').zfill(8)
            bits.extend([int(b) for b in bin_char])
        return bits

    def _bits_to_text(self, bits):
        """Convert a list of bits to text."""
        chars = []
        for i in range(0, len(bits), 8):
            byte = bits[i:i+8]
            if len(byte) < 8: break
            char_code = int(''.join(map(str, byte)), 2)
            if char_code == 0: break # End of message
            chars.append(chr(char_code))
        return ''.join(chars)

    def embed_watermark(self, image, text):
        """Embeds text data into the image using DCT."""
        # Note: We embed the text directly; the UI/App will handle hashing if needed
        # Convert to YCrCb and use Y channel (luminance) for watermarking
        img_ycc = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
        y_channel = img_ycc[:, :, 0].astype(np.float32)
        
        # Add a null terminator to the text
        text += '\0'
        bits = self._text_to_bits(text)
        
        h, w = y_channel.shape
        bit_idx = 0
        
        for i in range(0, h - self.block_size + 1, self.block_size):
            for j in range(0, w - self.block_size + 1, self.block_size):
                if bit_idx >= len(bits):
                    break
                
                block = y_channel[i:i+self.block_size, j:j+self.block_size]
                dct_block = cv2.dct(block)
                
                bit = bits[bit_idx]
                val1 = dct_block[self.coeff1]
                val2 = dct_block[self.coeff2]
                
                diff = 30 # Increased strength for robustness
                
                if bit == 1:
                    if val1 <= val2:
                        dct_block[self.coeff1] = val2 + diff
                else:
                    if val1 > val2:
                        dct_block[self.coeff2] = val1 + diff
                
                y_channel[i:i+self.block_size, j:j+self.block_size] = cv2.idct(dct_block)
                bit_idx += 1
            if bit_idx >= len(bits):
                break
                
        img_ycc[:, :, 0] = np.clip(y_channel, 0, 255).astype(np.uint8)
        return cv2.cvtColor(img_ycc, cv2.COLOR_YCrCb2BGR)

    def extract_watermark(self, image):
        """Extracts text data from a watermarked image."""
        img_ycc = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
        y_channel = img_ycc[:, :, 0].astype(np.float32)
        
        h, w = y_channel.shape
        bits = []
        
        for i in range(0, h - self.block_size + 1, self.block_size):
            for j in range(0, w - self.block_size + 1, self.block_size):
                block = y_channel[i:i+self.block_size, j:j+self.block_size]
                dct_block = cv2.dct(block)
                
                if dct_block[self.coeff1] > dct_block[self.coeff2]:
                    bits.append(1)
                else:
                    bits.append(0)
                
                if len(bits) % 8 == 0:
                    last_byte = bits[-8:]
                    if sum(last_byte) == 0:
                        return self._bits_to_text(bits)

        return self._bits_to_text(bits)

    def verify_integrity(self, image, original_text):
        """Extracts watermark and compares with the SHA-256 hash of the original text."""
        extracted_text = self.extract_watermark(image)
        if not extracted_text:
            return False, "No watermark found"
            
        # The watermark contains the text (which might be the hash itself)
        if "|" in extracted_text and "|" in original_text:
            # Multi-field check
            return extracted_text == original_text, extracted_text
        
        return extracted_text == original_text, extracted_text
