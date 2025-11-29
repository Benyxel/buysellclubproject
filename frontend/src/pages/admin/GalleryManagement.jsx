import React, { useState, useEffect } from "react";
import {
  FaPlus,
  FaEdit,
  FaTrash,
  FaImage,
  FaTimes,
  FaUpload,
  FaSearch,
  FaEye,
} from "react-icons/fa";
import { toast } from "react-toastify";
import API from "../../api";
import ConfirmModal from "../../components/shared/ConfirmModal";

const GalleryManagement = () => {
  const [galleryItems, setGalleryItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [itemToDelete, setItemToDelete] = useState(null);
  const [showImageModal, setShowImageModal] = useState(false);
  const [selectedImage, setSelectedImage] = useState(null);
  const [uploading, setUploading] = useState(false);

  const [formData, setFormData] = useState({
    title: "",
    description: "",
    image_url: "",
    category: "",
    is_featured: false,
    order: 0,
  });

  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState("");

  const fetchGalleryItems = async () => {
    try {
      setLoading(true);
      const resp = await API.get("/buysellapi/admin/gallery/");
      const data = Array.isArray(resp.data) ? resp.data : resp.data.results || [];
      setGalleryItems(data);
    } catch (error) {
      console.error("Error fetching gallery items:", error);
      if (error.response?.status === 401) {
        toast.error("Unauthorized. Please log in again.");
      } else {
        toast.error("Failed to fetch gallery items");
      }
      setGalleryItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGalleryItems();
  }, []);

  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value,
    }));
  };

  const handleImageFileChange = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      toast.error("Please upload a valid image file");
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      toast.error("Image size should be less than 10MB");
      return;
    }

    setImageFile(file);
    const reader = new FileReader();
    reader.onloadend = () => {
      setImagePreview(reader.result);
    };
    reader.readAsDataURL(file);
  };

  const uploadImage = async (file) => {
    const formData = new FormData();
    formData.append("image", file);
    formData.append("type", "gallery");

    try {
      const resp = await API.post("/buysellapi/admin/upload-image/", formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });
      return resp.data.image_url || resp.data.url;
    } catch (error) {
      console.error("Error uploading image:", error);
      throw error;
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!formData.title.trim()) {
      toast.error("Title is required");
      return;
    }

    if (!formData.image_url && !imageFile) {
      toast.error("Please provide an image URL or upload an image");
      return;
    }

    setUploading(true);
    try {
      let imageUrl = formData.image_url;

      // Upload image file if provided
      if (imageFile) {
        imageUrl = await uploadImage(imageFile);
      }

      const payload = {
        ...formData,
        image_url: imageUrl,
        order: parseInt(formData.order) || 0,
      };

      if (editing) {
        await API.patch(`/buysellapi/admin/gallery/${editing}/`, payload);
        toast.success("Gallery item updated successfully!");
      } else {
        await API.post("/buysellapi/admin/gallery/", payload);
        toast.success("Gallery item created successfully!");
      }

      resetForm();
      fetchGalleryItems();
    } catch (error) {
      console.error("Error saving gallery item:", error);
      console.error("Error response:", error.response?.data);
      const errorMessage = 
        error.response?.data?.error ||
        error.response?.data?.detail ||
        error.response?.data?.message ||
        error.message ||
        "Failed to save gallery item";
      toast.error(errorMessage);
    } finally {
      setUploading(false);
    }
  };

  const resetForm = () => {
    setFormData({
      title: "",
      description: "",
      image_url: "",
      category: "",
      is_featured: false,
      order: 0,
    });
    setImageFile(null);
    setImagePreview("");
    setEditing(null);
    setShowForm(false);
  };

  const handleEdit = (item) => {
    setFormData({
      title: item.title || "",
      description: item.description || "",
      image_url: item.image_url || "",
      category: item.category || "",
      is_featured: item.is_featured || false,
      order: item.order || 0,
    });
    setImageFile(null);
    setImagePreview(item.image_url || "");
    setEditing(item.id);
    setShowForm(true);
  };

  const handleDeleteClick = (item) => {
    setItemToDelete(item);
    setShowDeleteModal(true);
  };

  const handleDeleteConfirm = async () => {
    if (!itemToDelete) return;

    try {
      await API.delete(`/buysellapi/admin/gallery/${itemToDelete.id}/`);
      toast.success("Gallery item deleted successfully!");
      fetchGalleryItems();
    } catch (error) {
      console.error("Error deleting gallery item:", error);
      toast.error("Failed to delete gallery item");
    } finally {
      setShowDeleteModal(false);
      setItemToDelete(null);
    }
  };

  const handleViewImage = (item) => {
    setSelectedImage(item.image_url);
    setShowImageModal(true);
  };

  const filteredItems = galleryItems.filter((item) =>
    item.title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    item.description?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    item.category?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-800 dark:text-white">
          Gallery Management
        </h2>
        <button
          onClick={() => {
            resetForm();
            setShowForm(true);
          }}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          <FaPlus /> Add New Image
        </button>
      </div>

      {/* Search Bar */}
      <div className="mb-6">
        <div className="relative">
          <FaSearch className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search by title, description, or category..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
          />
        </div>
      </div>

      {/* Form Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-xl font-bold text-gray-800 dark:text-white">
                  {editing ? "Edit Gallery Item" : "Add New Gallery Item"}
                </h3>
                <button
                  onClick={resetForm}
                  className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                >
                  <FaTimes className="text-xl" />
                </button>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Title <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    name="title"
                    value={formData.title}
                    onChange={handleInputChange}
                    required
                    className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Description
                  </label>
                  <textarea
                    name="description"
                    value={formData.description}
                    onChange={handleInputChange}
                    rows={3}
                    className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Category
                  </label>
                  <input
                    type="text"
                    name="category"
                    value={formData.category}
                    onChange={handleInputChange}
                    placeholder="e.g., Products, Events, Team"
                    className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Image <span className="text-red-500">*</span>
                  </label>
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <FaUpload className="text-gray-400" />
                      <input
                        type="file"
                        accept="image/*"
                        onChange={handleImageFileChange}
                        className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                      />
                    </div>
                    <div className="text-sm text-gray-500 dark:text-gray-400">
                      OR
                    </div>
                    <input
                      type="url"
                      name="image_url"
                      value={formData.image_url}
                      onChange={handleInputChange}
                      placeholder="Enter image URL"
                      className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    />
                  </div>
                  {(imagePreview || formData.image_url) && (
                    <div className="mt-2">
                      <img
                        src={imagePreview || formData.image_url}
                        alt="Preview"
                        className="max-w-full h-48 object-contain rounded-lg border border-gray-300 dark:border-gray-600"
                      />
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-4">
                  <div className="flex items-center">
                    <input
                      type="checkbox"
                      name="is_featured"
                      checked={formData.is_featured}
                      onChange={handleInputChange}
                      className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                    />
                    <label className="ml-2 text-sm font-medium text-gray-700 dark:text-gray-300">
                      Featured Image
                    </label>
                  </div>

                  <div className="flex-1">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Display Order
                    </label>
                    <input
                      type="number"
                      name="order"
                      value={formData.order}
                      onChange={handleInputChange}
                      min="0"
                      className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    />
                  </div>
                </div>

                <div className="flex justify-end gap-3 pt-4">
                  <button
                    type="button"
                    onClick={resetForm}
                    className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={uploading}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {uploading ? "Saving..." : editing ? "Update" : "Create"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Image Preview Modal */}
      {showImageModal && (
        <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-auto">
            <div className="p-6">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-xl font-bold text-gray-800 dark:text-white">
                  Image Preview
                </h3>
                <button
                  onClick={() => setShowImageModal(false)}
                  className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                >
                  <FaTimes className="text-xl" />
                </button>
              </div>
              <img
                src={selectedImage}
                alt="Preview"
                className="max-w-full h-auto rounded-lg"
              />
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      <ConfirmModal
        isOpen={showDeleteModal}
        onClose={() => {
          setShowDeleteModal(false);
          setItemToDelete(null);
        }}
        onConfirm={handleDeleteConfirm}
        title="Delete Gallery Item"
        message={`Are you sure you want to delete "${itemToDelete?.title}"? This action cannot be undone.`}
      />

      {/* Gallery Grid */}
      {loading ? (
        <div className="flex justify-center items-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
        </div>
      ) : filteredItems.length === 0 ? (
        <div className="text-center py-12">
          <FaImage className="text-6xl text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400">
            {searchTerm ? "No gallery items found matching your search." : "No gallery items yet. Add your first image!"}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {filteredItems.map((item) => (
            <div
              key={item.id}
              className="bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden hover:shadow-lg transition-shadow"
            >
              <div className="relative aspect-square bg-gray-100 dark:bg-gray-700">
                <img
                  src={item.image_url}
                  alt={item.title}
                  className="w-full h-full object-cover"
                  onError={(e) => {
                    e.target.onerror = null;
                    e.target.src = "https://via.placeholder.com/400x400?text=Image+Not+Found";
                  }}
                />
                {item.is_featured && (
                  <div className="absolute top-2 right-2 bg-yellow-500 text-white px-2 py-1 rounded text-xs font-semibold">
                    Featured
                  </div>
                )}
                <div className="absolute inset-0 bg-black bg-opacity-0 hover:bg-opacity-30 transition-opacity flex items-center justify-center gap-2 opacity-0 hover:opacity-100">
                  <button
                    onClick={() => handleViewImage(item)}
                    className="p-2 bg-white rounded-full hover:bg-gray-100"
                    title="View Image"
                  >
                    <FaEye className="text-gray-800" />
                  </button>
                  <button
                    onClick={() => handleEdit(item)}
                    className="p-2 bg-blue-600 rounded-full hover:bg-blue-700"
                    title="Edit"
                  >
                    <FaEdit className="text-white" />
                  </button>
                  <button
                    onClick={() => handleDeleteClick(item)}
                    className="p-2 bg-red-600 rounded-full hover:bg-red-700"
                    title="Delete"
                  >
                    <FaTrash className="text-white" />
                  </button>
                </div>
              </div>
              <div className="p-4">
                <h3 className="font-semibold text-gray-800 dark:text-white mb-1 truncate">
                  {item.title}
                </h3>
                {item.category && (
                  <span className="inline-block px-2 py-1 bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 text-xs rounded mb-2">
                    {item.category}
                  </span>
                )}
                {item.description && (
                  <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-2">
                    {item.description}
                  </p>
                )}
                <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                  Order: {item.order}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default GalleryManagement;

