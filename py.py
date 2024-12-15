import tensorflow as tf
from tensorflow.keras import layers, models
import numpy as np
import os
from pymongo import MongoClient
from bson import ObjectId
from PIL import Image
import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# Check for GPU availability
print("GPU available:", tf.config.list_physical_devices("GPU"))

# Set parameters
img_width, img_height = 150, 150
epochs = 10

# Connect to MongoDB
client = MongoClient(
    "mongodb://localhost:27017/"
)  # Adjust the connection string as needed
db = client["plantanalysis_database"]  # Replace with your database name
collection = db["plant"]  # Replace with your collection name

# Load the trained model
model = models.load_model("plant_health_model.h5")

# Compile the model (if needed)
model.compile(loss="categorical_crossentropy", optimizer="adam", metrics=["accuracy"])

# Class to information mapping for plant health reports including medicines and application instructions
plant_info = {
    "healthy": {
        "problem": "No issues detected.",
        "cure": "N/A",
        "solution": "Keep monitoring.",
        "reason_for_damage": "N/A",
        "medicine": "N/A",
        "application": "N/A",
        "summary": "This plant is healthy and thriving.",
    },
    "diseased": {
        "problem": "Plant shows signs of disease.",
        "cure": "Apply appropriate fungicide.",
        "solution": "Isolate affected plants.",
        "reason_for_damage": "Fungal infection.",
        "medicine": "Fungicide ABC",
        "application": (
            "1. Identify affected areas.\n"
            "2. Mix 10ml of Fungicide ABC in 1 liter of water.\n"
            "3. Spray on affected areas every week.\n"
            "4. Isolate affected plants from healthy ones.\n"
            "5. Monitor plants for improvement."
        ),
        "summary": (
            "This plant has been diagnosed with a fungal infection that requires immediate attention."
        ),
    },
}


# Function to upload images to MongoDB
def upload_image_to_mongo(image_path):
    with open(image_path, "rb") as img_file:
        img_data = img_file.read()

    # Insert image data into MongoDB
    document = {"image_data": img_data, "filename": os.path.basename(image_path)}

    result = collection.insert_one(document)
    print(f"Uploaded {image_path} with id: {result.inserted_id}")


# Analyze plant image function to predict both class and plant name
def analyze_plant_image(img_array):
    predictions = model.predict(img_array, verbose=0)
    predicted_class_index = np.argmax(predictions[0])

    class_labels = [
        "healthy",
        "diseased",
    ]  # This should match your model's output classes
    predicted_class_label = class_labels[predicted_class_index]

    # Map to actual plant names (you need a mapping from index/class to actual plant names)
    plant_names = {
        0: "Rose",
        1: "Tomato",
        # Add more mappings according to your dataset...
    }

    predicted_plant_name = plant_names.get(predicted_class_index, "Unknown Plant")

    info = plant_info.get(predicted_class_label, None)

    if info:
        info["name"] = predicted_plant_name  # Add predicted plant name to info
        return predicted_class_label, info  # Return class label and info

    return None, {
        "error": f"No information available for class '{predicted_class_label}'."
    }


# Generate PDF report function without image section
def generate_pdf_report(plant_name, filename, result_info):
    pdf_filename = f"{plant_name}_health_report.pdf"

    c = canvas.Canvas(pdf_filename, pagesize=letter)
    width, height = letter

    # Title of the report centered at the top of the page
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, height - 50, "PlantifyLab Report")

    # Summary Section
    c.setFont("Helvetica", 12)
    c.drawString(100, height - 80, f"Plant Name: {result_info['name']}")

    # Analysis Result Section
    c.drawString(100, height - 100, f"Image Filename: {filename}")

    c.drawString(100, height - 130, f"Analysis Result:")

    if "error" in result_info:
        c.drawString(100, height - 150, result_info["error"])
    else:
        c.drawString(100, height - 150, f"Class: {result_info['class']}")
        c.drawString(100, height - 170, f"Problem: {result_info['problem']}")
        c.drawString(100, height - 190, f"Cure: {result_info['cure']}")
        c.drawString(
            100, height - 210, f"Suggested Medicine: {result_info['medicine']}"
        )

        # Administration Steps Section
        c.drawString(100, height - 230, f"Administration Steps:")

        steps = result_info["application"].split("\n")
        for i, step in enumerate(steps):
            c.drawString(120, height - (250 + i * 20), f"{i + 1}. {step}")

    # Summary Section
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, height - (250 + len(steps) * 20 + 30), f"Summary:")

    c.setFont("Helvetica", 12)
    summary_text = result_info["summary"]

    text_object = c.beginText(100, height - (250 + len(steps) * 20 + 50))

    for line in summary_text.split("\n"):
        text_object.textLine(line)

    c.drawText(text_object)

    # Save the PDF file.
    c.save()

    print(f"PDF report generated: {pdf_filename}")


# Process images from MongoDB and save results back to MongoDB
def process_images_from_db():
    cursor = collection.find()

    for document in cursor:
        img_data = document.get("image_data")  # Assuming image is stored as binary data
        if img_data:
            # Convert binary data back to an image and resize it
            img = Image.open(io.BytesIO(img_data)).convert(
                "RGB"
            )  # Ensure it is RGB format

            img_path = f"temp_image.jpg"
            img.save(img_path)  # Save the image temporarily for PDF generation

            img = img.resize((img_width, img_height))  # Resize to expected dimensions

            # Convert the image to a numpy array and normalize it
            img_array = np.array(img) / 255.0

            # Reshape for model input (1 sample, height, width, channels)
            img_array = img_array.reshape((1, img_width, img_height, 3))

            predicted_class_label, result_info = analyze_plant_image(img_array)

            # Update the document with analysis results in structured format
            collection.update_one(
                {"_id": ObjectId(document["_id"])},
                {"$set": {"analysis_result": result_info}},
            )

            # Extract plant name from filename (or ask user input)
            plant_name = os.path.splitext(document["filename"])[
                0
            ]  # Use filename without extension

            # Prepare result information for PDF generation
            if predicted_class_label:
                result_info["class"] = predicted_class_label

            generate_pdf_report(plant_name, document["filename"], result_info)


# Example usage: Upload an image to MongoDB before processing (replace with actual image path)
upload_image_to_mongo(
    "C:/Users/amit/OneDrive/Documents/python_code/website/websites/plant health analysis/new data set for try/sample images/0cc47b2d-4a92-4bbd-af46-945165dd1960___JR_FrgE.S 8586_new30degFlipLR.JPG"
)

# Run the processing function after uploading images
process_images_from_db()
