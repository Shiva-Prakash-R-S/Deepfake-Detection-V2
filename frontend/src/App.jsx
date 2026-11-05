import "./App.css";
import { useState } from "react";
import axios from "axios";
import { FaCloudUploadAlt, FaShieldAlt } from "react-icons/fa";

function App() {

  const [image, setImage] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);

  const [result, setResult] = useState(null);

  const [loading, setLoading] = useState(false);

  const handleImage = (e) => {

    const file = e.target.files[0];

    if(file){
      setSelectedFile(file);

      

      setImage(URL.createObjectURL(file));

    }

  };

  const detectImage = async () => {

    if (!selectedFile) return;

    const formData = new FormData();

    formData.append("image", selectedFile);

    setLoading(true);

    try {
        const apiUrl = window.location.port === "5000" ? "/predict" : "http://127.0.0.1:5000/predict";
        const response = await axios.post(
            apiUrl,
            formData
        );

        setResult(response.data);

    }

    catch(error){

        console.log(error);

        alert("Prediction Failed");

    }

    setLoading(false);

};

  return (

    <div className="app">

      {/* Navbar */}

      <nav className="navbar">

        <div className="logo">

          <FaShieldAlt/>

          <span>Deepfake Detection</span>

        </div>

      </nav>

      {/* Hero */}

      <div className="hero">

        <h1>AI Powered Deepfake Image Detection</h1>

        <p>

          Upload an image and our AI model will determine
          whether it is Real or Fake.

        </p>

        <div className="upload-card">

          {

            image ?

            <img
              src={image}
              className="preview"
              alt="preview"
            />

            :

            <>

            <FaCloudUploadAlt className="upload-icon"/>

            <h2>Drag & Drop Image</h2>

            <p>or</p>

            </>

          }

          <label className="choose-btn">

            Choose Image

            <input
              type="file"
              accept=".jpg,.jpeg,.png"
              hidden
              onChange={handleImage}
            />

          </label>

          {

            image &&

            <button
className="detect-btn"
onClick={detectImage}
>

{

loading ?

"Detecting..."

:

"Detect Image"

}

</button>



          }

          {

result &&

<div className="result-card">

<h2>

Prediction :
{" "}
{result.prediction}

</h2>

<p>

Confidence :
{result.confidence} %

</p>

<p>

Fake Probability :
{result.fake_probability} %

</p>

<p>

Real Probability :
{result.real_probability} %

</p>

<p>

Inference Time :
{result.inference_time} sec

</p>

<p>

Model :
{result.model}

</p>

</div>

}

        </div>

      </div>

    </div>

  );

}

export default App;