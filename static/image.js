document.addEventListener('DOMContentLoaded', () => {
    // Elements - YouTube Video
    const youtubeUrlInput = document.getElementById('youtubeUrl');
    const btnFetchInfo = document.getElementById('btnFetchInfo');
    const videoInfoBox = document.getElementById('videoInfoBox');
    const videoThumb = document.getElementById('videoThumb');
    const videoTitle = document.getElementById('videoTitle');
    const videoDuration = document.getElementById('videoDuration');

    // Elements - Image Upload
    const dropZone = document.getElementById('dropZone');
    const imageInput = document.getElementById('imageInput');
    const dropZoneContent = document.getElementById('dropZoneContent');
    const imagePreviewBox = document.getElementById('imagePreviewBox');
    const imagePreview = document.getElementById('imagePreview');
    const btnRemoveImg = document.getElementById('btnRemoveImg');

    // Accordion & Controls
    const toggleSettings = document.getElementById('toggleSettings');
    const settingsContent = document.getElementById('settingsContent');
    const layoutCards = document.querySelectorAll('.layout-card');
    const keyTolerance = document.getElementById('keyTolerance');
    const toleranceVal = document.getElementById('toleranceVal');
    const posOptions = document.querySelectorAll('.pos-option');
    const startTime = document.getElementById('startTime');
    const endTime = document.getElementById('endTime');
    
    const btnSubmit = document.getElementById('btnSubmit');

    // Status & Result
    const statusBox = document.getElementById('statusBox');
    const statusMessage = document.getElementById('statusMessage');
    const progressBar = document.getElementById('progressBar');
    
    const steps = [
        document.querySelector('.step-1'),
        document.querySelector('.step-2'),
        document.querySelector('.step-3')
    ];

    const resultBox = document.getElementById('resultBox');
    const outputVideoPlayer = document.getElementById('outputVideoPlayer');
    const downloadBtn = document.getElementById('downloadBtn');
    const errorBox = document.getElementById('errorBox');
    const errorMessage = document.getElementById('errorMessage');

    let selectedFile = null;

    // 1. Accordion Toggle
    if (toggleSettings && settingsContent) {
        toggleSettings.addEventListener('click', () => {
            settingsContent.classList.toggle('hidden');
            const icon = toggleSettings.querySelector('.arrow-icon');
            if (icon) {
                icon.classList.toggle('fa-chevron-down');
                icon.classList.toggle('fa-chevron-up');
            }
        });
    }

    // 2. Tolerance Slider
    if (keyTolerance && toleranceVal) {
        keyTolerance.addEventListener('input', (e) => {
            toleranceVal.textContent = e.target.value;
        });
    }

    // 3. Layout Cards Grid Selection
    if (layoutCards && layoutCards.length > 0) {
        layoutCards.forEach(card => {
            card.addEventListener('click', () => {
                layoutCards.forEach(c => c.classList.remove('active'));
                card.classList.add('active');
                const radio = card.querySelector('input[type="radio"]');
                if (radio) radio.checked = true;
            });
        });
    }

    // 4. Position Options Selection
    if (posOptions && posOptions.length > 0) {
        posOptions.forEach(opt => {
            opt.addEventListener('click', () => {
                posOptions.forEach(o => o.classList.remove('active'));
                opt.classList.add('active');
                const radio = opt.querySelector('input[type="radio"]');
                if (radio) radio.checked = true;
            });
        });
    }

    // 5. Fetch Info - YouTube Video
    if (btnFetchInfo && youtubeUrlInput) {
        btnFetchInfo.addEventListener('click', async () => {
            const url = youtubeUrlInput.value.trim();
            if (!url) {
                alert('يرجى إدخال رابط مقطع اليوتيوب أولاً');
                youtubeUrlInput.focus();
                return;
            }

            btnFetchInfo.disabled = true;
            btnFetchInfo.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> جاري التحقق...';

            try {
                const response = await fetch(`/api/info?url=${encodeURIComponent(url)}`);
                const data = await response.json();

                if (data.success && data.info) {
                    if (videoThumb) videoThumb.src = data.info.thumbnail || '';
                    if (videoTitle) videoTitle.textContent = data.info.title || 'مقطع اليوتيوب';
                    if (videoDuration) videoDuration.textContent = data.info.duration_string || 'غير محدد';
                    if (videoInfoBox) videoInfoBox.classList.remove('hidden');
                } else {
                    alert('تعذر جلب معلومات المقطع: ' + (data.detail || 'تأكد من صحة الرابط.'));
                }
            } catch (err) {
                alert('حدث خطأ أثناء فحص الرابط.');
            } finally {
                btnFetchInfo.disabled = false;
                btnFetchInfo.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i> فحص الرابط';
            }
        });
    }

    // 6. Drag & Drop Image Handling
    if (dropZone && imageInput) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            }, false);
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => dropZone.classList.add('drag-over'), false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => dropZone.classList.remove('drag-over'), false);
        });

        dropZone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt ? dt.files : null;
            if (files && files.length > 0) {
                handleImageFile(files[0]);
            }
        });

        imageInput.addEventListener('change', (e) => {
            if (e.target.files && e.target.files.length > 0) {
                handleImageFile(e.target.files[0]);
            }
        });

        function handleImageFile(file) {
            if (!file.type.startsWith('image/')) {
                alert('يرجى اختيار ملف صورة صالح (JPG, PNG, WEBP)');
                return;
            }
            selectedFile = file;
            try {
                const dataTransfer = new DataTransfer();
                dataTransfer.items.add(file);
                imageInput.files = dataTransfer.files;
            } catch (err) {
                console.log('DataTransfer fallback', err);
            }
            const reader = new FileReader();
            reader.onload = (e) => {
                if (imagePreview) imagePreview.src = e.target.result;
                if (dropZoneContent) dropZoneContent.classList.add('hidden');
                if (imagePreviewBox) imagePreviewBox.classList.remove('hidden');
            };
            reader.readAsDataURL(file);
        }

        if (btnRemoveImg) {
            btnRemoveImg.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                selectedFile = null;
                imageInput.value = '';
                if (imagePreview) imagePreview.src = '';
                if (imagePreviewBox) imagePreviewBox.classList.add('hidden');
                if (dropZoneContent) dropZoneContent.classList.remove('hidden');
            });
        }
    }

    // 7. Submit Form & Process Job
    if (btnSubmit) {
        btnSubmit.addEventListener('click', async () => {
            const youtubeUrl = youtubeUrlInput ? youtubeUrlInput.value.trim() : '';
            if (!youtubeUrl) {
                alert('يرجى إدخال رابط فيديو اليوتيوب أولاً');
                if (youtubeUrlInput) youtubeUrlInput.focus();
                return;
            }
            
            const fileToUpload = selectedFile || (imageInput && imageInput.files && imageInput.files[0]);
            if (!fileToUpload) {
                alert('يرجى رفع الصورة المطلوبة');
                return;
            }

            const selectedLayoutRadio = document.querySelector('input[name="layout"]:checked');
            const layout = selectedLayoutRadio ? selectedLayoutRadio.value : 'black_screen_transparent';
            const tol = keyTolerance ? keyTolerance.value : 0.25;
            const selectedPosRadio = document.querySelector('input[name="video_position"]:checked');
            const pos = selectedPosRadio ? selectedPosRadio.value : 'center';
            const sTime = startTime ? (startTime.value || 0) : 0;
            const eTime = endTime ? (endTime.value || '') : '';

            // Reset UI State
            btnSubmit.disabled = true;
            if (statusBox) statusBox.classList.remove('hidden');
            if (resultBox) resultBox.classList.add('hidden');
            if (errorBox) errorBox.classList.add('hidden');
            
            if (steps) {
                steps.forEach(s => s && s.classList.remove('active', 'completed'));
                if (steps[0]) steps[0].classList.add('active');
            }
            if (progressBar) progressBar.style.width = '10%';
            if (statusMessage) statusMessage.textContent = 'جاري وضع الطلب في قائمة الانتظار...';
            
            if (statusBox) statusBox.scrollIntoView({ behavior: 'smooth' });

            // Prepare Form Data for Backend
            const formData = new FormData();
            formData.append('youtube_url', youtubeUrl);
            formData.append('image', fileToUpload);
            formData.append('layout', layout);
            formData.append('key_tolerance', tol);
            formData.append('video_position', pos);
            formData.append('start_time', sTime);
            if (eTime) {
                formData.append('end_time', eTime);
            }

            try {
                const response = await fetch('/api/generate', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (data.success && data.task_id) {
                    pollTaskStatus(data.task_id);
                } else {
                    showError(data.detail || 'فشل بدء الطلب. يرجى المحاولة مرة أخرى.');
                }
            } catch (err) {
                showError('تعذر الاتصال بالخادم. تأكد من أن الموقع يعمل وحدّث الصفحة.');
            }
        });
    }

    function pollTaskStatus(taskId) {
        const MAX_POLLING_ATTEMPTS = 300; // 10 minutes at 2s interval
        const MAX_CONSECUTIVE_ERRORS = 5;
        let pollCount = 0;
        let errorCount = 0;

        const interval = setInterval(async () => {
            pollCount++;

            if (pollCount >= MAX_POLLING_ATTEMPTS) {
                clearInterval(interval);
                showError('انتهى وقت الانتظار. استغرقت العملية وقتاً أطول من المعتاد.');
                return;
            }

            try {
                const res = await fetch(`/api/status/${taskId}`);
                if (!res.ok) throw new Error('Network response was not ok');
                const data = await res.json();
                
                errorCount = 0; 

                if (data.status === 'downloading') {
                    if (statusMessage) statusMessage.textContent = data.message;
                    if (progressBar) progressBar.style.width = '30%';
                    if (steps[0]) steps[0].classList.add('active');
                } else if (data.status === 'processing') {
                    if (statusMessage) statusMessage.textContent = data.message;
                    if (progressBar) progressBar.style.width = '70%';
                    if (steps[0]) steps[0].classList.replace('active', 'completed');
                    if (steps[1]) steps[1].classList.add('active');
                } else if (data.status === 'completed') {
                    clearInterval(interval);
                    if (progressBar) progressBar.style.width = '100%';
                    if (steps[1]) steps[1].classList.replace('active', 'completed');
                    if (steps[2]) steps[2].classList.add('completed');
                    
                    setTimeout(() => {
                        if (statusBox) statusBox.classList.add('hidden');
                        if (resultBox) resultBox.classList.remove('hidden');
                        if (outputVideoPlayer) outputVideoPlayer.src = data.download_url;
                        if (downloadBtn) downloadBtn.href = data.download_url;
                        if (btnSubmit) btnSubmit.disabled = false;
                        if (resultBox) resultBox.scrollIntoView({ behavior: 'smooth' });
                    }, 1000);
                    
                } else if (data.status === 'failed') {
                    clearInterval(interval);
                    showError(data.message || 'حدث خطأ أثناء المعالجة.');
                }
            } catch (e) {
                console.error('Polling error:', e);
                errorCount++;
                if (errorCount >= MAX_CONSECUTIVE_ERRORS) {
                    clearInterval(interval);
                    showError('فقد الاتصال بالخادم. يرجى المحاولة مرة أخرى.');
                }
            }
        }, 2000);
    }

    function showError(msg) {
        if (statusBox) statusBox.classList.add('hidden');
        if (errorBox && errorMessage) {
            errorMessage.textContent = msg;
            errorBox.classList.remove('hidden');
            errorBox.scrollIntoView({ behavior: 'smooth' });
        } else {
            alert(msg);
        }
        if (btnSubmit) btnSubmit.disabled = false;
    }
});
